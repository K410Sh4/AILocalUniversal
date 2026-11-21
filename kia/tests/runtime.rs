use kia_cognitive_runtime::{
    AdaptiveCognitiveNetwork, CognitiveCapability, CognitiveConnection, CognitiveFeedback,
    CognitiveRequest, CognitiveRuntime, ComponentExecutor, ComponentId, ConnectionKind,
    ExecutionTarget, ExecutorRegistry, FeedbackOutcome, NetworkNode, NeuralComponent,
    NeuralComponentKind, ProcessingProfile, ResourceBudget, ResourceSnapshot, ResourceVector,
    CONTRACT_SCHEMA_VERSION,
};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

fn snapshot() -> ResourceSnapshot {
    ResourceSnapshot {
        total: ResourceVector {
            cpu_millis: 8_000,
            ram_bytes: 16_000_000_000,
            gpu_millis: 4_000,
            vram_bytes: 8_000_000_000,
            npu_units: 1,
        },
        available: ResourceVector {
            cpu_millis: 8_000,
            ram_bytes: 12_000_000_000,
            gpu_millis: 3_000,
            vram_bytes: 6_000_000_000,
            npu_units: 1,
        },
        available_targets: vec![ExecutionTarget::Cpu, ExecutionTarget::Gpu],
    }
}

fn capability() -> CognitiveCapability {
    CognitiveCapability {
        id: "mathematics".into(),
        name: "Matemática".to_owned(),
        domain: "reasoning".to_owned(),
        intent_tags: BTreeSet::from(["calculation".to_owned(), "math".to_owned()]),
        context_tags: BTreeSet::from(["cost_estimate".to_owned()]),
        enabled: true,
    }
}

fn component(
    id: &str,
    kind: NeuralComponentKind,
    cost: ResourceVector,
    baseline_quality: f32,
) -> NeuralComponent {
    NeuralComponent {
        id: id.into(),
        name: id.to_owned(),
        kind,
        supported_capabilities: BTreeSet::from(["mathematics".into()]),
        context_tags: BTreeSet::from(["cost_estimate".to_owned()]),
        execution_target: ExecutionTarget::Cpu,
        estimated_cost: cost,
        resource_estimate_available: true,
        baseline_quality,
        enabled: true,
        metadata: BTreeMap::new(),
    }
}

fn request() -> CognitiveRequest {
    CognitiveRequest {
        schema_version: CONTRACT_SCHEMA_VERSION,
        request_id: "req-001".to_owned(),
        intent: "calculation".to_owned(),
        context_tags: BTreeSet::from(["cost_estimate".to_owned()]),
        required_capabilities: vec!["mathematics".into()],
        input: json!({"units": 250, "unit_cost": 12.5}),
        max_components: 4,
    }
}

fn network() -> AdaptiveCognitiveNetwork {
    let mut network = AdaptiveCognitiveNetwork::default();
    network.add_capability(capability()).unwrap();
    let calculator = component(
        "local-calculator",
        NeuralComponentKind::DeterministicTool,
        ResourceVector {
            cpu_millis: 100,
            ram_bytes: 1_000_000,
            ..ResourceVector::default()
        },
        0.95,
    );
    network.add_component(calculator).unwrap();
    network
        .add_connection(CognitiveConnection {
            from: NetworkNode::Capability("mathematics".into()),
            to: NetworkNode::Component("local-calculator".into()),
            kind: ConnectionKind::Supports,
            weight: 0.9,
            observations: 10,
            successes: 9,
        })
        .unwrap();
    network
}

struct MockExecutor;

impl ComponentExecutor for MockExecutor {
    fn execute(
        &self,
        request: &CognitiveRequest,
        _component: &NeuralComponent,
    ) -> Result<Value, String> {
        let units = request.input["units"].as_u64().unwrap_or_default();
        let unit_cost = request.input["unit_cost"].as_f64().unwrap_or_default();
        Ok(json!({"total_cost": units as f64 * unit_cost}))
    }
}

#[test]
fn planner_selects_a_registered_component_and_reserves_its_resources() {
    let network = network();
    let snapshot = snapshot();
    let budget = ResourceBudget::new(
        ResourceVector {
            cpu_millis: 4_000,
            ram_bytes: 4_000_000_000,
            ..ResourceVector::default()
        },
        &snapshot,
    )
    .unwrap();
    let mut registry = ExecutorRegistry::default();
    registry.register(ComponentId::from("local-calculator"), MockExecutor);
    let runtime = CognitiveRuntime::new(network, snapshot, budget, registry).unwrap();

    let plan = runtime.plan(&request()).unwrap();

    assert_eq!(plan.selections.len(), 1);
    assert_eq!(
        plan.selections[0].component_id,
        ComponentId::from("local-calculator")
    );
    assert_eq!(plan.reserved_resources.cpu_millis, 100);
    assert!(plan.selections[0].routing_score > 0.8);
}

#[test]
fn runtime_executes_without_copying_user_payload_into_telemetry() {
    let snapshot = snapshot();
    let budget = ResourceBudget::from_profile(&snapshot, ProcessingProfile::Medium).unwrap();
    let mut registry = ExecutorRegistry::default();
    registry.register(ComponentId::from("local-calculator"), MockExecutor);
    let runtime = CognitiveRuntime::new(network(), snapshot, budget, registry).unwrap();

    let report = runtime.execute(&request()).unwrap();

    assert!(report.complete);
    assert_eq!(report.outputs[0].value["total_cost"], json!(3125.0));
    let serialized = serde_json::to_string(&report).unwrap();
    assert!(!serialized.contains("unit_cost"));
    assert_eq!(
        report.events[0].status,
        kia_cognitive_runtime::ExecutionStatus::Completed
    );
}

#[test]
fn planner_rejects_components_that_exceed_the_resource_budget() {
    let mut network = AdaptiveCognitiveNetwork::default();
    network.add_capability(capability()).unwrap();
    network
        .add_component(component(
            "oversized-model",
            NeuralComponentKind::LanguageModel,
            ResourceVector {
                cpu_millis: 2_000,
                ram_bytes: 10_000_000_000,
                ..ResourceVector::default()
            },
            1.0,
        ))
        .unwrap();
    let snapshot = snapshot();
    let budget = ResourceBudget::new(
        ResourceVector {
            cpu_millis: 4_000,
            ram_bytes: 2_000_000_000,
            ..ResourceVector::default()
        },
        &snapshot,
    )
    .unwrap();
    let mut registry = ExecutorRegistry::default();
    registry.register(ComponentId::from("oversized-model"), MockExecutor);
    let runtime = CognitiveRuntime::new(network, snapshot, budget, registry).unwrap();

    assert!(matches!(
        runtime.plan(&request()),
        Err(kia_cognitive_runtime::RuntimeError::NoEligibleComponent(id))
            if id == kia_cognitive_runtime::CapabilityId::from("mathematics")
    ));
}

#[test]
fn unmeasured_components_are_not_selected_as_zero_cost() {
    let mut network = AdaptiveCognitiveNetwork::default();
    network.add_capability(capability()).unwrap();
    let mut unknown = component(
        "unknown-cost",
        NeuralComponentKind::LanguageModel,
        ResourceVector::default(),
        1.0,
    );
    unknown.resource_estimate_available = false;
    network.add_component(unknown).unwrap();
    let snapshot = snapshot();
    let budget = ResourceBudget::from_profile(&snapshot, ProcessingProfile::Ultra).unwrap();
    let mut registry = ExecutorRegistry::default();
    registry.register(ComponentId::from("unknown-cost"), MockExecutor);
    let runtime = CognitiveRuntime::new(network, snapshot, budget, registry).unwrap();

    assert!(matches!(
        runtime.plan(&request()),
        Err(kia_cognitive_runtime::RuntimeError::NoEligibleComponent(_))
    ));
}

#[test]
fn evaluated_feedback_changes_connection_priority_and_versions_the_network() {
    let mut network = network();
    let original_version = network.version();
    let feedback = CognitiveFeedback {
        capability_id: "mathematics".into(),
        component_id: "local-calculator".into(),
        outcome: FeedbackOutcome::Success,
        validation_ref: "validation-run-001".to_owned(),
        notes: Some("Replay determinístico aprovado.".to_owned()),
    };

    let update = network.record_evaluated_feedback(feedback, 0.2).unwrap();

    assert!(update.updated_weight > update.previous_weight);
    assert_eq!(update.observations, 11);
    assert!(network.version() > original_version);
}

#[test]
fn feedback_without_an_independent_validation_reference_is_rejected() {
    let mut network = network();
    let feedback = CognitiveFeedback {
        capability_id: "mathematics".into(),
        component_id: "local-calculator".into(),
        outcome: FeedbackOutcome::Success,
        validation_ref: " ".to_owned(),
        notes: None,
    };

    assert!(network.record_evaluated_feedback(feedback, 0.1).is_err());
}

#[test]
fn processing_profiles_set_only_the_logical_cpu_budget() {
    let snapshot = snapshot();
    let light = ResourceBudget::from_profile(&snapshot, ProcessingProfile::Light).unwrap();
    let ultra = ResourceBudget::from_profile(&snapshot, ProcessingProfile::Ultra).unwrap();

    assert_eq!(light.max.cpu_millis, 2_640);
    assert_eq!(ultra.max.cpu_millis, 7_600);
    assert_eq!(light.max.vram_bytes, snapshot.available.vram_bytes);
    assert_eq!(light.max.ram_bytes, snapshot.available.ram_bytes);
}

#[test]
fn unsupported_contract_schema_is_rejected_before_planning() {
    let mut invalid = request();
    invalid.schema_version += 1;
    assert!(invalid.validate().is_err());
}

#[test]
fn sequential_plan_reserves_peak_resources_instead_of_summing_components() {
    use kia_cognitive_runtime::CognitiveCapability;

    let mut network = AdaptiveCognitiveNetwork::default();
    network.add_capability(capability()).unwrap();
    network
        .add_capability(CognitiveCapability {
            id: "programming".into(),
            name: "Programação".to_owned(),
            domain: "software".to_owned(),
            intent_tags: BTreeSet::from(["programming".to_owned()]),
            context_tags: BTreeSet::new(),
            enabled: true,
        })
        .unwrap();

    let mut calculator = component(
        "local-calculator",
        NeuralComponentKind::DeterministicTool,
        ResourceVector {
            cpu_millis: 300,
            ram_bytes: 1_000_000_000,
            ..ResourceVector::default()
        },
        0.95,
    );
    calculator.supported_capabilities = BTreeSet::from(["mathematics".into()]);
    network.add_component(calculator).unwrap();

    let mut programmer = component(
        "local-programmer",
        NeuralComponentKind::NeuralSpecialist,
        ResourceVector {
            cpu_millis: 300,
            ram_bytes: 2_000_000_000,
            ..ResourceVector::default()
        },
        0.9,
    );
    programmer.supported_capabilities = BTreeSet::from(["programming".into()]);
    network.add_component(programmer).unwrap();

    let snapshot = ResourceSnapshot {
        total: ResourceVector {
            cpu_millis: 1000,
            ram_bytes: 4_000_000_000,
            ..ResourceVector::default()
        },
        available: ResourceVector {
            cpu_millis: 1000,
            ram_bytes: 4_000_000_000,
            ..ResourceVector::default()
        },
        available_targets: vec![ExecutionTarget::Cpu],
    };
    let budget = ResourceBudget::new(
        ResourceVector {
            cpu_millis: 400,
            ram_bytes: 3_000_000_000,
            ..ResourceVector::default()
        },
        &snapshot,
    )
    .unwrap();
    let mut registry = ExecutorRegistry::default();
    registry.register(ComponentId::from("local-calculator"), MockExecutor);
    registry.register(ComponentId::from("local-programmer"), MockExecutor);
    let runtime = CognitiveRuntime::new(network, snapshot, budget, registry).unwrap();
    let mut request = request();
    request.required_capabilities.push("programming".into());
    request.intent = "calculation and programming".to_owned();

    let plan = runtime.plan(&request).unwrap();

    assert_eq!(plan.selections.len(), 2);
    assert_eq!(plan.reserved_resources.cpu_millis, 300);
    assert_eq!(plan.reserved_resources.ram_bytes, 2_000_000_000);
}

#[test]
fn feedback_history_is_bounded_to_recent_4096_evaluations() {
    let mut network = network();
    for index in 0..4097 {
        network
            .record_evaluated_feedback(
                CognitiveFeedback {
                    capability_id: "mathematics".into(),
                    component_id: "local-calculator".into(),
                    outcome: FeedbackOutcome::Success,
                    validation_ref: format!("validation-{index}"),
                    notes: Some("resultado determinístico reproduzido".to_owned()),
                },
                0.05,
            )
            .unwrap();
    }

    assert_eq!(network.feedback_history().len(), 4096);
    assert_eq!(
        network.feedback_history().first().unwrap().validation_ref,
        "validation-1"
    );
    assert_eq!(
        network.feedback_history().last().unwrap().validation_ref,
        "validation-4096"
    );
}
