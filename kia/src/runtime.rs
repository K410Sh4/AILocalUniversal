use crate::{
    AdaptiveCognitiveNetwork, CognitiveRequest, ExecutionControl, ExecutionControlError,
    ExecutionLeaseManager, ExecutorRegistry, LeaseError, PlannedComponent, ResourceBudget,
    ResourceSnapshot,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fmt::{Display, Formatter};
use std::time::Instant;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionStatus {
    Completed,
    Failed,
    Cancelled,
    TimedOut,
    AdmissionRejected,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExecutionEvent {
    pub component_id: crate::ComponentId,
    pub capabilities: Vec<crate::CapabilityId>,
    pub status: ExecutionStatus,
    pub duration_ms: u64,
    pub estimated_cost: crate::ResourceVector,
    /// Não contém prompt, texto de usuário ou conteúdo documental.
    pub detail: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ComponentOutput {
    pub component_id: crate::ComponentId,
    pub capabilities: Vec<crate::CapabilityId>,
    pub value: Value,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ComponentFailure {
    pub component_id: crate::ComponentId,
    pub capabilities: Vec<crate::CapabilityId>,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExecutionReport {
    pub request_id: String,
    pub plan: crate::ExecutionPlan,
    pub outputs: Vec<ComponentOutput>,
    pub failures: Vec<ComponentFailure>,
    pub events: Vec<ExecutionEvent>,
    pub complete: bool,
}

pub struct CognitiveRuntime {
    network: AdaptiveCognitiveNetwork,
    snapshot: ResourceSnapshot,
    budget: ResourceBudget,
    executors: ExecutorRegistry,
}

#[derive(Debug, Clone, PartialEq)]
pub enum RuntimeError {
    InvalidRequest(String),
    InvalidResources(crate::ResourceError),
    BudgetExceedsAvailability,
    UnknownCapability(crate::CapabilityId),
    NoEligibleComponent(crate::CapabilityId),
    ExecutionAdmission(String),
}

impl Display for RuntimeError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for RuntimeError {}

impl CognitiveRuntime {
    pub fn new(
        network: AdaptiveCognitiveNetwork,
        snapshot: ResourceSnapshot,
        budget: ResourceBudget,
        executors: ExecutorRegistry,
    ) -> Result<Self, RuntimeError> {
        snapshot
            .validate()
            .map_err(RuntimeError::InvalidResources)?;
        if !budget.max.fits_within(&snapshot.available) {
            return Err(RuntimeError::BudgetExceedsAvailability);
        }
        Ok(Self {
            network,
            snapshot,
            budget,
            executors,
        })
    }

    pub fn network(&self) -> &AdaptiveCognitiveNetwork {
        &self.network
    }

    pub fn network_mut(&mut self) -> &mut AdaptiveCognitiveNetwork {
        &mut self.network
    }

    pub fn plan(&self, request: &CognitiveRequest) -> Result<crate::ExecutionPlan, RuntimeError> {
        crate::planner::build_plan(
            &self.network,
            request,
            &self.snapshot,
            &self.budget,
            |component_id| self.executors.contains(component_id),
        )
    }

    /// Mantém a execução sequencial legada com um lease privado por tarefa.
    pub fn execute(&self, request: &CognitiveRequest) -> Result<ExecutionReport, RuntimeError> {
        let control = ExecutionControl::unbounded();
        let leases = ExecutionLeaseManager::new(self.budget.max, 1, 0)
            .map_err(|error| RuntimeError::ExecutionAdmission(error.to_string()))?;
        self.execute_with_control(request, &control, &leases)
    }

    /// Executa um plano respeitando cancelamento, deadline e admissão compartilhada.
    ///
    /// Para limitar tarefas concorrentes, execuções independentes devem compartilhar o
    /// mesmo ExecutionLeaseManager. Cada plano permanece sequencial; o paralelismo é entre
    /// tarefas e só ocorre dentro dos limites de leases fornecidos.
    pub fn execute_with_control(
        &self,
        request: &CognitiveRequest,
        control: &ExecutionControl,
        leases: &ExecutionLeaseManager,
    ) -> Result<ExecutionReport, RuntimeError> {
        let plan = self.plan(request)?;
        let mut outputs = Vec::new();
        let mut failures = Vec::new();
        let mut events = Vec::new();

        for selection in &plan.selections {
            let component = self
                .network
                .components()
                .get(&selection.component_id)
                .expect("planner only selects registered components");
            let executor = self
                .executors
                .get(&selection.component_id)
                .expect("planner only selects components with an executor");
            let started = Instant::now();

            if let Err(error) = control.check() {
                record_control_failure(
                    selection,
                    error,
                    started.elapsed().as_millis() as u64,
                    &mut failures,
                    &mut events,
                );
                break;
            }

            let _lease = match leases.acquire(selection.estimated_cost, control) {
                Ok(lease) => lease,
                Err(error) => {
                    let status = match error {
                        LeaseError::Cancelled => ExecutionStatus::Cancelled,
                        LeaseError::DeadlineExceeded => ExecutionStatus::TimedOut,
                        _ => ExecutionStatus::AdmissionRejected,
                    };
                    let reason = error.to_string();
                    failures.push(ComponentFailure {
                        component_id: selection.component_id.clone(),
                        capabilities: selection.capabilities.clone(),
                        reason: reason.clone(),
                    });
                    events.push(event(
                        selection,
                        status,
                        started.elapsed().as_millis() as u64,
                        Some(reason),
                    ));
                    break;
                }
            };

            let result = executor.execute_controlled(request, component, control);
            if let Err(error) = control.check() {
                record_control_failure(
                    selection,
                    error,
                    started.elapsed().as_millis() as u64,
                    &mut failures,
                    &mut events,
                );
                break;
            }

            match result {
                Ok(value) => {
                    let duration_ms = started.elapsed().as_millis() as u64;
                    outputs.push(ComponentOutput {
                        component_id: selection.component_id.clone(),
                        capabilities: selection.capabilities.clone(),
                        value,
                    });
                    events.push(event(
                        selection,
                        ExecutionStatus::Completed,
                        duration_ms,
                        None,
                    ));
                }
                Err(reason) => {
                    let duration_ms = started.elapsed().as_millis() as u64;
                    failures.push(ComponentFailure {
                        component_id: selection.component_id.clone(),
                        capabilities: selection.capabilities.clone(),
                        reason: reason.clone(),
                    });
                    events.push(event(
                        selection,
                        ExecutionStatus::Failed,
                        duration_ms,
                        Some(reason),
                    ));
                }
            }
        }

        Ok(ExecutionReport {
            request_id: request.request_id.clone(),
            complete: failures.is_empty() && events.len() == plan.selections.len(),
            plan,
            outputs,
            failures,
            events,
        })
    }
}

fn record_control_failure(
    selection: &PlannedComponent,
    error: ExecutionControlError,
    duration_ms: u64,
    failures: &mut Vec<ComponentFailure>,
    events: &mut Vec<ExecutionEvent>,
) {
    let status = match error {
        ExecutionControlError::Cancelled => ExecutionStatus::Cancelled,
        ExecutionControlError::DeadlineExceeded => ExecutionStatus::TimedOut,
    };
    let reason = error.to_string();
    failures.push(ComponentFailure {
        component_id: selection.component_id.clone(),
        capabilities: selection.capabilities.clone(),
        reason: reason.clone(),
    });
    events.push(event(selection, status, duration_ms, Some(reason)));
}

fn event(
    selection: &PlannedComponent,
    status: ExecutionStatus,
    duration_ms: u64,
    detail: Option<String>,
) -> ExecutionEvent {
    ExecutionEvent {
        component_id: selection.component_id.clone(),
        capabilities: selection.capabilities.clone(),
        status,
        duration_ms,
        estimated_cost: selection.estimated_cost,
        detail,
    }
}
