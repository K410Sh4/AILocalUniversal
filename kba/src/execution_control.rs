use crate::ResourceVector;
use std::fmt::{Display, Formatter};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant};

const WAIT_POLL_INTERVAL: Duration = Duration::from_millis(25);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExecutionControlError {
    Cancelled,
    DeadlineExceeded,
}

impl Display for ExecutionControlError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Cancelled => write!(formatter, "Tarefa cancelada."),
            Self::DeadlineExceeded => write!(formatter, "Prazo da tarefa excedido."),
        }
    }
}

impl std::error::Error for ExecutionControlError {}

#[derive(Clone)]
pub struct ExecutionControl {
    inner: Arc<ExecutionControlState>,
}

struct ExecutionControlState {
    cancelled: AtomicBool,
    deadline: Option<Instant>,
}

impl ExecutionControl {
    /// Cria controle limitado por um prazo contado a partir deste instante.
    pub fn with_timeout(timeout: Duration) -> Self {
        let now = Instant::now();
        Self {
            inner: Arc::new(ExecutionControlState {
                cancelled: AtomicBool::new(false),
                deadline: Some(now.checked_add(timeout).unwrap_or(now)),
            }),
        }
    }

    /// Cria controle sem deadline; ainda pode ser cancelado explicitamente.
    pub fn unbounded() -> Self {
        Self {
            inner: Arc::new(ExecutionControlState {
                cancelled: AtomicBool::new(false),
                deadline: None,
            }),
        }
    }

    pub fn cancel(&self) {
        self.inner.cancelled.store(true, Ordering::Release);
    }

    pub fn is_cancelled(&self) -> bool {
        self.inner.cancelled.load(Ordering::Acquire)
    }

    pub fn is_timed_out(&self) -> bool {
        self.inner
            .deadline
            .is_some_and(|deadline| Instant::now() >= deadline)
    }

    pub fn remaining(&self) -> Option<Duration> {
        self.inner
            .deadline
            .map(|deadline| deadline.saturating_duration_since(Instant::now()))
    }

    pub fn check(&self) -> Result<(), ExecutionControlError> {
        if self.is_cancelled() {
            return Err(ExecutionControlError::Cancelled);
        }
        if self.is_timed_out() {
            return Err(ExecutionControlError::DeadlineExceeded);
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LeaseError {
    InvalidConfiguration,
    RequestExceedsCapacity,
    QueueFull,
    Cancelled,
    DeadlineExceeded,
    ResourceOverflow,
    Poisoned,
}

impl Display for LeaseError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for LeaseError {}

impl From<ExecutionControlError> for LeaseError {
    fn from(error: ExecutionControlError) -> Self {
        match error {
            ExecutionControlError::Cancelled => Self::Cancelled,
            ExecutionControlError::DeadlineExceeded => Self::DeadlineExceeded,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExecutionLeaseSnapshot {
    pub capacity: ResourceVector,
    pub reserved: ResourceVector,
    pub active: usize,
    pub waiting: usize,
    pub max_active: usize,
    pub max_waiters: usize,
}

#[derive(Default)]
struct LeaseState {
    reserved: ResourceVector,
    active: usize,
    waiting: usize,
}

struct LeaseManagerInner {
    capacity: ResourceVector,
    max_active: usize,
    max_waiters: usize,
    state: Mutex<LeaseState>,
    changed: Condvar,
}

#[derive(Clone)]
pub struct ExecutionLeaseManager {
    inner: Arc<LeaseManagerInner>,
}

impl ExecutionLeaseManager {
    pub fn new(
        capacity: ResourceVector,
        max_active: usize,
        max_waiters: usize,
    ) -> Result<Self, LeaseError> {
        if max_active == 0 {
            return Err(LeaseError::InvalidConfiguration);
        }
        Ok(Self {
            inner: Arc::new(LeaseManagerInner {
                capacity,
                max_active,
                max_waiters,
                state: Mutex::new(LeaseState::default()),
                changed: Condvar::new(),
            }),
        })
    }

    pub fn acquire(
        &self,
        cost: ResourceVector,
        control: &ExecutionControl,
    ) -> Result<ExecutionLease, LeaseError> {
        control.check()?;
        if !cost.fits_within(&self.inner.capacity) {
            return Err(LeaseError::RequestExceedsCapacity);
        }

        let mut state = self.inner.state.lock().map_err(|_| LeaseError::Poisoned)?;
        if state.waiting == 0 && self.can_grant(&state, cost) {
            reserve(&mut state, cost)?;
            return Ok(self.lease(cost));
        }
        if state.waiting >= self.inner.max_waiters {
            return Err(LeaseError::QueueFull);
        }

        state.waiting += 1;
        loop {
            if let Err(error) = control.check() {
                state.waiting -= 1;
                self.inner.changed.notify_all();
                return Err(error.into());
            }

            if self.can_grant(&state, cost) {
                state.waiting -= 1;
                reserve(&mut state, cost)?;
                self.inner.changed.notify_all();
                return Ok(self.lease(cost));
            }

            let wait_for = control
                .remaining()
                .unwrap_or(WAIT_POLL_INTERVAL)
                .min(WAIT_POLL_INTERVAL);
            let (next_state, _) = self
                .inner
                .changed
                .wait_timeout(state, wait_for)
                .map_err(|_| LeaseError::Poisoned)?;
            state = next_state;
        }
    }

    pub fn snapshot(&self) -> Result<ExecutionLeaseSnapshot, LeaseError> {
        let state = self.inner.state.lock().map_err(|_| LeaseError::Poisoned)?;
        Ok(ExecutionLeaseSnapshot {
            capacity: self.inner.capacity,
            reserved: state.reserved,
            active: state.active,
            waiting: state.waiting,
            max_active: self.inner.max_active,
            max_waiters: self.inner.max_waiters,
        })
    }

    fn can_grant(&self, state: &LeaseState, cost: ResourceVector) -> bool {
        state.active < self.inner.max_active
            && state
                .reserved
                .checked_add(&cost)
                .is_some_and(|next| next.fits_within(&self.inner.capacity))
    }

    fn lease(&self, cost: ResourceVector) -> ExecutionLease {
        ExecutionLease {
            manager: self.clone(),
            cost,
        }
    }

    fn release(&self, cost: ResourceVector) {
        if let Ok(mut state) = self.inner.state.lock() {
            state.reserved = ResourceVector {
                cpu_millis: state.reserved.cpu_millis.saturating_sub(cost.cpu_millis),
                ram_bytes: state.reserved.ram_bytes.saturating_sub(cost.ram_bytes),
                gpu_millis: state.reserved.gpu_millis.saturating_sub(cost.gpu_millis),
                vram_bytes: state.reserved.vram_bytes.saturating_sub(cost.vram_bytes),
                npu_units: state.reserved.npu_units.saturating_sub(cost.npu_units),
            };
            state.active = state.active.saturating_sub(1);
            self.inner.changed.notify_all();
        }
    }
}

fn reserve(state: &mut LeaseState, cost: ResourceVector) -> Result<(), LeaseError> {
    state.reserved = state
        .reserved
        .checked_add(&cost)
        .ok_or(LeaseError::ResourceOverflow)?;
    state.active = state
        .active
        .checked_add(1)
        .ok_or(LeaseError::ResourceOverflow)?;
    Ok(())
}

pub struct ExecutionLease {
    manager: ExecutionLeaseManager,
    cost: ResourceVector,
}

impl ExecutionLease {
    pub fn cost(&self) -> ResourceVector {
        self.cost
    }
}

impl Drop for ExecutionLease {
    fn drop(&mut self) {
        self.manager.release(self.cost);
    }
}
