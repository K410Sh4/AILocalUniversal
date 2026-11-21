use kia_cognitive_runtime::{
    AdaptiveCognitiveNetwork, CognitiveCapability, CognitiveConnection, CognitiveRequest,
    CognitiveRuntime, ComponentExecutor, ComponentId, ConnectionKind, ExecutionControl,
    ExecutionLeaseManager, ExecutionStatus, ExecutionTarget, ExecutorRegistry, NetworkNode,
    NeuralComponent, NeuralComponentKind, ResourceBudget, ResourceSnapshot, ResourceVector,
    CONTRACT_SCHEMA_VERSION,
};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{mpsc, Arc};
use std::thread;
use std::time::{Duration, Instant};

fn setup<E: ComponentExecutor + 'static>(
    executor: E,
) -> (CognitiveRuntime, ResourceSnapshot, ResourceBudget) {
    let mut network = AdaptiveCognitiveNetwork::default();
    network
        .add_capability(CognitiveCapability {
            id: "reasoning".into(),
            name: "Raciocínio".to_owned(),
            domain: "reasoning".to_owned(),
            intent_tags: BTreeSet::from(["test".to_owned()]),
            context_tags: BTreeSet::new(),
            enabled: true,
        })
        .unwrap();
    let component = NeuralComponent {
        id: "test-component".into(),
        name: "Executor de teste".to_owned(),
        kind: NeuralComponentKind::DeterministicTool,
        supported_capabilities: BTreeSet::from(["reasoning".into()]),
        context_tags: BTreeSet::new(),
        execution_target: ExecutionTarget::Cpu,
        estimated_cost: ResourceVector {
            cpu_millis: 200,
            ram_bytes: 1024,
            ..ResourceVector::default()
        },
        resource_estimate_available: true,
        baseline_quality: 0.9,
        enabled: true,
        metadata: BTreeMap::new(),
    };
    network.add_component(component).unwrap();
    network
        .add_connection(CognitiveConnection {
            from: NetworkNode::Capability("reasoning".into()),
            to: NetworkNode::Component("test-component".into()),
            kind: ConnectionKind::Supports,
            weight: 0.9,
            observations: 1,
            successes: 1,
        })
        .unwrap();

    let snapshot = ResourceSnapshot {
        total: ResourceVector {
            cpu_millis: 2000,
            ram_bytes: 1_000_000,
            ..ResourceVector::default()
        },
        available: ResourceVector {
            cpu_millis: 2000,
            ram_bytes: 1_000_000,
            ..ResourceVector::default()
        },
        available_targets: vec![ExecutionTarget::Cpu],
    };
    let budget = ResourceBudget::new(
        ResourceVector {
            cpu_millis: 1000,
            ram_bytes: 500_000,
            ..ResourceVector::default()
        },
        &snapshot,
    )
    .unwrap();
    let mut executors = ExecutorRegistry::default();
    executors.register(ComponentId::from("test-component"), executor);
    let runtime = CognitiveRuntime::new(network, snapshot.clone(), budget, executors).unwrap();
    (runtime, snapshot, budget)
}

fn request() -> CognitiveRequest {
    CognitiveRequest {
        schema_version: CONTRACT_SCHEMA_VERSION,
        request_id: "controlled-task".to_owned(),
        intent: "test".to_owned(),
        context_tags: BTreeSet::new(),
        required_capabilities: vec!["reasoning".into()],
        input: json!({"value": 7}),
        max_components: 1,
    }
}

struct FastExecutor {
    calls: Arc<AtomicUsize>,
}

impl ComponentExecutor for FastExecutor {
    fn execute(
        &self,
        _request: &CognitiveRequest,
        _component: &NeuralComponent,
    ) -> Result<Value, String> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        Ok(json!({"ok": true}))
    }
}

struct CooperativeExecutor {
    started: mpsc::Sender<()>,
}

impl ComponentExecutor for CooperativeExecutor {
    fn execute(
        &self,
        _request: &CognitiveRequest,
        _component: &NeuralComponent,
    ) -> Result<Value, String> {
        Err("execute legado não deveria ser chamado".to_owned())
    }

    fn execute_controlled(
        &self,
        _request: &CognitiveRequest,
        _component: &NeuralComponent,
        control: &ExecutionControl,
    ) -> Result<Value, String> {
        let _ = self.started.send(());
        loop {
            control.check().map_err(|error| error.to_string())?;
            thread::sleep(Duration::from_millis(5));
        }
    }
}

fn wait_for_waiter(manager: &ExecutionLeaseManager) {
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        if manager.snapshot().unwrap().waiting == 1 {
            return;
        }
        assert!(Instant::now() < deadline, "a tarefa não entrou na fila");
        thread::sleep(Duration::from_millis(2));
    }
}

#[test]
fn leases_enforce_resource_capacity_and_release_with_raii() {
    let capacity = ResourceVector {
        cpu_millis: 1000,
        ram_bytes: 4096,
        ..ResourceVector::default()
    };
    let manager = ExecutionLeaseManager::new(capacity, 1, 0).unwrap();
    let control = ExecutionControl::unbounded();
    let lease = manager
        .acquire(
            ResourceVector {
                cpu_millis: 600,
                ram_bytes: 2048,
                ..ResourceVector::default()
            },
            &control,
        )
        .unwrap();

    assert_eq!(manager.snapshot().unwrap().active, 1);
    assert_eq!(manager.snapshot().unwrap().reserved.cpu_millis, 600);
    assert_eq!(
        manager
            .acquire(ResourceVector::default(), &control)
            .err()
            .unwrap(),
        kia_cognitive_runtime::LeaseError::QueueFull
    );

    drop(lease);
    let snapshot = manager.snapshot().unwrap();
    assert_eq!(snapshot.active, 0);
    assert_eq!(snapshot.reserved, ResourceVector::default());
}

#[test]
fn bounded_wait_queue_rejects_new_work_when_full() {
    let capacity = ResourceVector {
        cpu_millis: 1000,
        ..ResourceVector::default()
    };
    let manager = ExecutionLeaseManager::new(capacity, 1, 1).unwrap();
    let control = ExecutionControl::unbounded();
    let lease = manager.acquire(capacity, &control).unwrap();
    let worker_manager = manager.clone();
    let worker_control = control.clone();
    let (tx, rx) = mpsc::channel();
    let worker = thread::spawn(move || {
        let result = worker_manager.acquire(
            ResourceVector {
                cpu_millis: 100,
                ..ResourceVector::default()
            },
            &worker_control,
        );
        let _ = tx.send(result.map(|lease| drop(lease)));
    });

    wait_for_waiter(&manager);
    assert_eq!(
        manager.acquire(ResourceVector::default(), &control).err().unwrap(),
        kia_cognitive_runtime::LeaseError::QueueFull
    );
    control.cancel();
    assert_eq!(
        rx.recv_timeout(Duration::from_secs(2)).unwrap(),
        Err(kia_cognitive_runtime::LeaseError::Cancelled)
    );
    worker.join().unwrap();
    drop(lease);
    assert_eq!(manager.snapshot().unwrap().waiting, 0);
}

#[test]
fn deadline_expires_while_waiting_for_a_lease() {
    let capacity = ResourceVector {
        cpu_millis: 1000,
        ..ResourceVector::default()
    };
    let manager = ExecutionLeaseManager::new(capacity, 1, 1).unwrap();
    let holder = manager
        .acquire(capacity, &ExecutionControl::unbounded())
        .unwrap();
    let control = ExecutionControl::with_timeout(Duration::from_millis(40));

    assert_eq!(
        manager
            .acquire(ResourceVector::default(), &control)
            .err()
            .unwrap(),
        kia_cognitive_runtime::LeaseError::DeadlineExceeded
    );
    assert_eq!(manager.snapshot().unwrap().waiting, 0);
    drop(holder);
}

#[test]
fn runtime_rejects_dispatch_after_task_deadline() {
    let calls = Arc::new(AtomicUsize::new(0));
    let (runtime, snapshot, budget) = setup(FastExecutor {
        calls: calls.clone(),
    });
    let leases = ExecutionLeaseManager::new(budget.max, 1, 0).unwrap();
    let control = ExecutionControl::with_timeout(Duration::ZERO);

    let report = runtime
        .execute_with_control(&request(), &control, &leases)
        .unwrap();

    assert!(!report.complete);
    assert_eq!(calls.load(Ordering::SeqCst), 0);
    assert_eq!(report.events[0].status, ExecutionStatus::TimedOut);
    assert_eq!(leases.snapshot().unwrap().active, 0);
    assert_eq!(snapshot.available_targets, vec![ExecutionTarget::Cpu]);
}

#[test]
fn cooperative_adapter_observes_cancellation_during_execution() {
    let (started_tx, started_rx) = mpsc::channel();
    let (runtime, _snapshot, budget) = setup(CooperativeExecutor {
        started: started_tx,
    });
    let leases = ExecutionLeaseManager::new(budget.max, 1, 1).unwrap();
    let control = ExecutionControl::unbounded();
    let worker_control = control.clone();
    let worker_leases = leases.clone();
    let (report_tx, report_rx) = mpsc::channel();
    let worker = thread::spawn(move || {
        let report = runtime.execute_with_control(&request(), &worker_control, &worker_leases);
        let _ = report_tx.send(report);
    });

    started_rx.recv_timeout(Duration::from_secs(2)).unwrap();
    control.cancel();
    let report = report_rx
        .recv_timeout(Duration::from_secs(2))
        .unwrap()
        .unwrap();

    assert!(!report.complete);
    assert_eq!(report.events[0].status, ExecutionStatus::Cancelled);
    assert_eq!(leases.snapshot().unwrap().active, 0);
    worker.join().unwrap();
}
