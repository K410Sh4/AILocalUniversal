use kia_cognitive_runtime::{
    AdaptiveCognitiveNetwork, CognitiveCapability, CognitiveConnection, ComponentId,
    ConnectionKind, ExecutionTarget, HostState, NetworkNode, NeuralComponent, NeuralComponentKind,
    ResourceBudget, ResourceSnapshot, ResourceVector,
};
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};
use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};

fn state() -> HostState {
    let mut network = AdaptiveCognitiveNetwork::default();
    network
        .add_capability(CognitiveCapability {
            id: "mathematics".into(),
            name: "Matemática".to_owned(),
            domain: "reasoning".to_owned(),
            intent_tags: BTreeSet::from(["calculation".to_owned()]),
            context_tags: BTreeSet::new(),
            enabled: true,
        })
        .unwrap();
    network
        .add_component(NeuralComponent {
            id: "local-calculator".into(),
            name: "Calculadora local".to_owned(),
            kind: NeuralComponentKind::DeterministicTool,
            supported_capabilities: BTreeSet::from(["mathematics".into()]),
            context_tags: BTreeSet::new(),
            execution_target: ExecutionTarget::Cpu,
            estimated_cost: ResourceVector {
                cpu_millis: 100,
                ram_bytes: 1024,
                ..ResourceVector::default()
            },
            resource_estimate_available: true,
            baseline_quality: 0.9,
            enabled: true,
            metadata: BTreeMap::new(),
        })
        .unwrap();
    network
        .add_connection(CognitiveConnection {
            from: NetworkNode::Capability("mathematics".into()),
            to: NetworkNode::Component("local-calculator".into()),
            kind: ConnectionKind::Supports,
            weight: 0.8,
            observations: 4,
            successes: 4,
        })
        .unwrap();

    let resources = ResourceSnapshot {
        total: ResourceVector {
            cpu_millis: 4000,
            ram_bytes: 8_000_000,
            ..ResourceVector::default()
        },
        available: ResourceVector {
            cpu_millis: 4000,
            ram_bytes: 8_000_000,
            ..ResourceVector::default()
        },
        available_targets: vec![ExecutionTarget::Cpu],
    };
    let budget = ResourceBudget::new(
        ResourceVector {
            cpu_millis: 2000,
            ram_bytes: 4_000_000,
            ..ResourceVector::default()
        },
        &resources,
    )
    .unwrap();
    HostState {
        network,
        resources,
        budget,
        available_executors: BTreeSet::from([ComponentId::from("local-calculator")]),
    }
}

fn send(writer: &mut impl Write, value: serde_json::Value) {
    serde_json::to_writer(&mut *writer, &value).unwrap();
    writeln!(writer).unwrap();
    writer.flush().unwrap();
}

fn read(reader: &mut impl BufRead) -> serde_json::Value {
    let mut line = String::new();
    reader.read_line(&mut line).unwrap();
    serde_json::from_str(&line).unwrap()
}

#[test]
fn host_process_handles_health_state_sync_plan_and_shutdown_over_jsonl() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_kia-runtime-host"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    let mut output = BufReader::new(child.stdout.take().unwrap());

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "health-1",
            "command": {"type": "health"}
        }),
    );
    let health = read(&mut output);
    assert_eq!(health["ok"], true);
    assert_eq!(health["request_id"], "health-1");
    assert_eq!(health["result"]["service"], "kia-cognitive-runtime");
    assert_eq!(health["result"]["protocol_version"], 2);

    let state = serde_json::to_value(state()).unwrap();
    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "state-1",
            "command": {
                "type": "replace_state",
                "payload": {"state": state}
            }
        }),
    );
    let replaced = read(&mut output);
    assert_eq!(replaced["ok"], true);
    assert_eq!(replaced["result"]["capability_count"], 1);
    assert_eq!(replaced["result"]["component_count"], 1);

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "plan-1",
            "command": {
                "type": "plan",
                "payload": {
                    "request": {
                        "schema_version": 1,
                        "request_id": "task-1",
                        "intent": "calculation",
                        "context_tags": [],
                        "required_capabilities": ["mathematics"],
                        "input": {"number": 42},
                        "max_components": 2
                    }
                }
            }
        }),
    );
    let plan = read(&mut output);
    assert_eq!(plan["ok"], true);
    assert_eq!(
        plan["result"]["selections"][0]["component_id"],
        "local-calculator"
    );

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "feedback-1",
            "command": {
                "type": "record_feedback",
                "payload": {
                    "feedback": {
                        "capability_id": "mathematics",
                        "component_id": "local-calculator",
                        "outcome": "success",
                        "validation_ref": "independent-validation-1",
                        "notes": null
                    },
                    "learning_rate": 0.2
                }
            }
        }),
    );
    let feedback = read(&mut output);
    assert_eq!(feedback["ok"], true);
    assert!(feedback["result"]["updated_weight"].as_f64().unwrap() > 0.8);

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "inspect-1",
            "command": {"type": "inspect"}
        }),
    );
    let inspection = read(&mut output);
    assert_eq!(inspection["result"]["feedback_count"], 1);
    assert_eq!(inspection["result"]["network_version"], 4);

    // Uma sincronização normal não pode zerar a prioridade aprendida.
    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "state-2",
            "command": {
                "type": "replace_state",
                "payload": {"state": state}
            }
        }),
    );
    let resynced = read(&mut output);
    assert_eq!(resynced["ok"], true);
    assert_eq!(resynced["result"]["feedback_count"], 1);
    assert_eq!(resynced["result"]["network_version"], 4);

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "plan-2",
            "command": {
                "type": "plan",
                "payload": {
                    "request": {
                        "schema_version": 1,
                        "request_id": "task-2",
                        "intent": "calculation",
                        "context_tags": [],
                        "required_capabilities": ["mathematics"],
                        "input": {"number": 42},
                        "max_components": 2
                    }
                }
            }
        }),
    );
    let plan_after_learning = read(&mut output);
    assert_eq!(plan_after_learning["ok"], true);
    assert!(
        plan_after_learning["result"]["selections"][0]["routing_score"]
            .as_f64()
            .unwrap()
            > plan["result"]["selections"][0]["routing_score"]
                .as_f64()
                .unwrap()
    );

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "shutdown-1",
            "command": {"type": "shutdown"}
        }),
    );
    let shutdown = read(&mut output);
    assert_eq!(shutdown["ok"], true);
    drop(input);
    assert!(child.wait().unwrap().success());
}

#[test]
fn host_rejects_unsupported_protocol_versions() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_kia-runtime-host"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    let mut output = BufReader::new(child.stdout.take().unwrap());

    send(
        &mut input,
        json!({
            "protocol_version": 99,
            "request_id": "future-1",
            "command": {"type": "health"}
        }),
    );
    let response = read(&mut output);
    assert_eq!(response["ok"], false);
    assert_eq!(response["error"]["code"], "unsupported_protocol");

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "shutdown-2",
            "command": {"type": "shutdown"}
        }),
    );
    let _ = read(&mut output);
    drop(input);
    assert!(child.wait().unwrap().success());
}


#[test]
fn host_restores_persisted_learning_before_fresh_resource_state_and_exports_it() {
    use kia_cognitive_runtime::{CognitiveFeedback, FeedbackOutcome};

    let mut persisted_network = state().network;
    persisted_network
        .record_evaluated_feedback(
            CognitiveFeedback {
                capability_id: "mathematics".into(),
                component_id: "local-calculator".into(),
                outcome: FeedbackOutcome::Success,
                validation_ref: "persisted-validation-1".to_owned(),
                notes: None,
            },
            0.5,
        )
        .unwrap();
    let persisted = serde_json::to_value(persisted_network).unwrap();

    let mut child = Command::new(env!("CARGO_BIN_EXE_kia-runtime-host"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    let mut output = BufReader::new(child.stdout.take().unwrap());

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "restore-1",
            "command": {
                "type": "restore_learning",
                "payload": {"network": persisted}
            }
        }),
    );
    let restored = read(&mut output);
    assert_eq!(restored["ok"], true);
    assert_eq!(restored["result"]["feedback_count"], 1);

    // O estado operacional novo substitui recursos/executores, mas conserva a
    // prioridade e a avaliação já persistidas no snapshot cognitivo.
    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "replace-1",
            "command": {
                "type": "replace_state",
                "payload": {"state": serde_json::to_value(state()).unwrap()}
            }
        }),
    );
    let replaced = read(&mut output);
    assert_eq!(replaced["ok"], true);
    assert_eq!(replaced["result"]["feedback_count"], 1);

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "export-1",
            "command": {"type": "export_network"}
        }),
    );
    let exported = read(&mut output);
    assert_eq!(exported["ok"], true);
    assert_eq!(exported["result"]["network"]["feedback_history"].as_array().unwrap().len(), 1);
    assert!(
        exported["result"]["network"]["connections"][0]["weight"]
            .as_f64()
            .unwrap()
            > 0.8
    );
    assert_eq!(
        exported["result"]["network"]["connections"][0]["observations"],
        5
    );

    send(
        &mut input,
        json!({
            "protocol_version": 2,
            "request_id": "shutdown-restore",
            "command": {"type": "shutdown"}
        }),
    );
    let _ = read(&mut output);
    drop(input);
    assert!(child.wait().unwrap().success());
}
