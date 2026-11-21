use crate::{
    plan_with_executor_ids, AdaptiveCognitiveNetwork, CognitiveFeedback, CognitiveRequest,
    ComponentId, ResourceBudget, ResourceSnapshot, CONTRACT_SCHEMA_VERSION,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeSet;

pub const HOST_PROTOCOL_VERSION: u16 = 1;
pub const MAX_REQUEST_BYTES: usize = 4 * 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HostState {
    pub network: AdaptiveCognitiveNetwork,
    pub resources: ResourceSnapshot,
    pub budget: ResourceBudget,
    /// IDs para os quais a aplicação possui um executor/adaptador registrado.
    pub available_executors: BTreeSet<ComponentId>,
}

impl HostState {
    pub fn validate(&self) -> Result<(), HostError> {
        self.network
            .validate()
            .map_err(|error| HostError::new("invalid_network", error.to_string()))?;
        self.resources
            .validate()
            .map_err(|error| HostError::new("invalid_resources", error.to_string()))?;
        if !self.budget.max.fits_within(&self.resources.available) {
            return Err(HostError::new(
                "invalid_budget",
                "O orçamento excede os recursos declarados como disponíveis.",
            ));
        }
        for component_id in &self.available_executors {
            let component = self.network.components().get(component_id).ok_or_else(|| {
                HostError::new(
                    "unknown_executor_component",
                    format!("Executor referencia componente inexistente: {component_id}"),
                )
            })?;
            if !component.enabled {
                return Err(HostError::new(
                    "disabled_executor_component",
                    format!("Componente desativado não pode ter executor ativo: {component_id}"),
                ));
            }
        }
        Ok(())
    }
}

#[derive(Debug, Deserialize)]
pub struct HostRequest {
    pub protocol_version: u16,
    pub request_id: String,
    pub command: HostCommand,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", content = "payload", rename_all = "snake_case")]
pub enum HostCommand {
    Health,
    ReplaceState { state: HostState },
    Plan { request: CognitiveRequest },
    RecordFeedback {
        feedback: CognitiveFeedback,
        learning_rate: f32,
    },
    Inspect,
    Shutdown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HostError {
    pub code: String,
    pub message: String,
}

impl HostError {
    fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }
}

#[derive(Debug, Serialize)]
pub struct HostResponse {
    pub protocol_version: u16,
    pub request_id: String,
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<HostError>,
}

impl HostResponse {
    fn success(request_id: String, result: Value) -> Self {
        Self {
            protocol_version: HOST_PROTOCOL_VERSION,
            request_id,
            ok: true,
            result: Some(result),
            error: None,
        }
    }

    fn failure(request_id: String, error: HostError) -> Self {
        Self {
            protocol_version: HOST_PROTOCOL_VERSION,
            request_id,
            ok: false,
            result: None,
            error: Some(error),
        }
    }
}

#[derive(Default)]
pub struct RuntimeHost {
    state: Option<HostState>,
}

impl RuntimeHost {
    pub fn process_line(&mut self, line: &str) -> (HostResponse, bool) {
        if line.len() > MAX_REQUEST_BYTES {
            return (
                HostResponse::failure(
                    String::new(),
                    HostError::new("request_too_large", "A solicitação excede 4 MiB."),
                ),
                false,
            );
        }

        let request: HostRequest = match serde_json::from_str(line) {
            Ok(request) => request,
            Err(error) => {
                return (
                    HostResponse::failure(
                        String::new(),
                        HostError::new("invalid_json", format!("JSONL inválido: {error}")),
                    ),
                    false,
                );
            }
        };

        if request.request_id.trim().is_empty()
            || request.request_id.len() > 128
            || !request.request_id.chars().all(|character| {
                character.is_ascii_alphanumeric()
                    || matches!(character, '-' | '_' | '.' | ':')
            })
        {
            return (
                HostResponse::failure(
                    String::new(),
                    HostError::new("invalid_request_id", "request_id inválido."),
                ),
                false,
            );
        }
        if request.protocol_version != HOST_PROTOCOL_VERSION {
            return (
                HostResponse::failure(
                    request.request_id,
                    HostError::new(
                        "unsupported_protocol",
                        format!(
                            "Versão recebida {}, suportada {}.",
                            request.protocol_version, HOST_PROTOCOL_VERSION
                        ),
                    ),
                ),
                false,
            );
        }

        self.dispatch(request.request_id, request.command)
    }

    fn dispatch(
        &mut self,
        request_id: String,
        command: HostCommand,
    ) -> (HostResponse, bool) {
        match command {
            HostCommand::Health => (
                HostResponse::success(
                    request_id,
                    json!({
                        "service": "kia-cognitive-runtime",
                        "version": env!("CARGO_PKG_VERSION"),
                        "protocol_version": HOST_PROTOCOL_VERSION,
                        "contract_schema_version": CONTRACT_SCHEMA_VERSION
                    }),
                ),
                false,
            ),
            HostCommand::ReplaceState { state } => {
                if let Err(error) = state.validate() {
                    return (HostResponse::failure(request_id, error), false);
                }
                let result = json!({
                    "network_version": state.network.version(),
                    "capability_count": state.network.capabilities().len(),
                    "component_count": state.network.components().len(),
                    "connection_count": state.network.connections().len(),
                    "available_executor_count": state.available_executors.len()
                });
                self.state = Some(state);
                (HostResponse::success(request_id, result), false)
            }
            HostCommand::Plan { request } => {
                let Some(state) = self.state.as_ref() else {
                    return (
                        HostResponse::failure(
                            request_id,
                            HostError::new("state_not_configured", "Envie replace_state antes de plan."),
                        ),
                        false,
                    );
                };
                match plan_with_executor_ids(
                    &state.network,
                    &request,
                    &state.resources,
                    &state.budget,
                    &state.available_executors,
                ) {
                    Ok(plan) => {
                        let result = serde_json::to_value(plan).unwrap_or(Value::Null);
                        (HostResponse::success(request_id, result), false)
                    }
                    Err(error) => (
                        HostResponse::failure(
                            request_id,
                            HostError::new("planning_failed", error.to_string()),
                        ),
                        false,
                    ),
                }
            }
            HostCommand::RecordFeedback {
                feedback,
                learning_rate,
            } => {
                let Some(state) = self.state.as_mut() else {
                    return (
                        HostResponse::failure(
                            request_id,
                            HostError::new(
                                "state_not_configured",
                                "Envie replace_state antes de registrar feedback.",
                            ),
                        ),
                        false,
                    );
                };
                match state.network.record_evaluated_feedback(feedback, learning_rate) {
                    Ok(update) => (
                        HostResponse::success(
                            request_id,
                            json!({
                                "previous_weight": update.previous_weight,
                                "updated_weight": update.updated_weight,
                                "observations": update.observations,
                                "network_version": state.network.version()
                            }),
                        ),
                        false,
                    ),
                    Err(error) => (
                        HostResponse::failure(
                            request_id,
                            HostError::new("feedback_rejected", error.to_string()),
                        ),
                        false,
                    ),
                }
            }
            HostCommand::Inspect => {
                let Some(state) = self.state.as_ref() else {
                    return (
                        HostResponse::failure(
                            request_id,
                            HostError::new("state_not_configured", "Nenhuma rede foi configurada."),
                        ),
                        false,
                    );
                };
                let result = json!({
                    "network_version": state.network.version(),
                    "capability_ids": state.network.capabilities().keys().collect::<Vec<_>>(),
                    "component_ids": state.network.components().keys().collect::<Vec<_>>(),
                    "connection_count": state.network.connections().len(),
                    "feedback_count": state.network.feedback_history().len(),
                    "available_executor_ids": state.available_executors,
                    "resource_budget": state.budget.max,
                    "available_resources": state.resources.available,
                    "available_targets": state.resources.available_targets
                });
                (HostResponse::success(request_id, result), false)
            }
            HostCommand::Shutdown => (
                HostResponse::success(request_id, json!({"shutdown": true})),
                true,
            ),
        }
    }
}
