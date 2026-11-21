use crate::{CapabilityId, ComponentId, ExecutionTarget, ResourceVector};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

pub const CONTRACT_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CognitiveCapability {
    pub id: CapabilityId,
    pub name: String,
    pub domain: String,
    /// Rótulos declarativos de intenção; não são probabilidades.
    pub intent_tags: BTreeSet<String>,
    pub context_tags: BTreeSet<String>,
    pub enabled: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NeuralComponentKind {
    LanguageModel,
    DeterministicTool,
    NeuralSpecialist,
    Adapter,
    Memory,
    Preprocessor,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NeuralComponent {
    pub id: ComponentId,
    pub name: String,
    pub kind: NeuralComponentKind,
    pub supported_capabilities: BTreeSet<CapabilityId>,
    pub context_tags: BTreeSet<String>,
    pub execution_target: ExecutionTarget,
    pub estimated_cost: ResourceVector,
    /// false impede seleção quando custo ou perfil físico ainda é desconhecido.
    pub resource_estimate_available: bool,
    /// Prior de avaliação entre 0 e 1; não é uma medida de probabilidade.
    pub baseline_quality: f32,
    pub enabled: bool,
    pub metadata: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(tag = "node_type", content = "id", rename_all = "snake_case")]
pub enum NetworkNode {
    Capability(CapabilityId),
    Component(ComponentId),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConnectionKind {
    Supports,
    Requires,
    DelegatesTo,
    Complements,
    FallbackTo,
    ProducesInputFor,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CognitiveConnection {
    pub from: NetworkNode,
    pub to: NetworkNode,
    pub kind: ConnectionKind,
    /// Prioridade operacional entre 0 e 1, não probabilidade.
    pub weight: f32,
    pub observations: u64,
    pub successes: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FeedbackOutcome {
    Success,
    Partial,
    Failure,
}

impl FeedbackOutcome {
    pub const fn target(self) -> f32 {
        match self {
            Self::Success => 1.0,
            Self::Partial => 0.5,
            Self::Failure => 0.0,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CognitiveFeedback {
    pub capability_id: CapabilityId,
    pub component_id: ComponentId,
    pub outcome: FeedbackOutcome,
    /// Identificador da avaliação independente que justifica o sinal de aprendizado.
    pub validation_ref: String,
    pub notes: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CognitiveRequest {
    pub schema_version: u16,
    pub request_id: String,
    pub intent: String,
    pub context_tags: BTreeSet<String>,
    pub required_capabilities: Vec<CapabilityId>,
    /// Conteúdo encaminhado ao adaptador. Nunca é copiado para o trace do runtime.
    pub input: Value,
    pub max_components: usize,
}

impl CognitiveRequest {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != CONTRACT_SCHEMA_VERSION {
            return Err("Versão de contrato CognitiveRequest não suportada.".to_owned());
        }
        if self.request_id.trim().is_empty() {
            return Err("request_id não pode ficar vazio.".to_owned());
        }
        if self.intent.trim().is_empty() {
            return Err("intent não pode ficar vazia.".to_owned());
        }
        if self.required_capabilities.is_empty() {
            return Err("A solicitação precisa indicar ao menos uma capacidade.".to_owned());
        }
        if self.max_components == 0 {
            return Err("max_components precisa ser positivo.".to_owned());
        }
        let mut unique = BTreeSet::new();
        if self.required_capabilities.iter().any(|capability| {
            !capability.is_valid() || !unique.insert(capability)
        }) {
            return Err("A solicitação contém IDs inválidos ou capacidades duplicadas.".to_owned());
        }
        Ok(())
    }
}
