//! K.IA Cognitive Runtime — núcleo operacional inicial da Artificial Brain.
//!
//! Esta crate oferece contratos serializáveis, rede de capacidades, seleção seletiva,
//! orçamento lógico de recursos e feedback avaliado. Motores externos são conectados
//! por implementações de ComponentExecutor.

mod executor;
mod ids;
mod network;
mod planner;
mod resources;
mod runtime;
mod types;

pub use executor::{ComponentExecutor, ExecutorRegistry};
pub use ids::{CapabilityId, ComponentId};
pub use network::{AdaptiveCognitiveNetwork, NetworkError, PlasticityUpdate};
pub use planner::{ExecutionPlan, PlannedComponent};
pub use resources::{
    ExecutionTarget, ProcessingProfile, ResourceBudget, ResourceError, ResourceSnapshot,
    ResourceVector,
};
pub use runtime::{
    CognitiveRuntime, ComponentFailure, ComponentOutput, ExecutionEvent, ExecutionReport,
    ExecutionStatus, RuntimeError,
};
pub use types::{
    CognitiveCapability, CognitiveConnection, CognitiveFeedback, CognitiveRequest, ConnectionKind,
    FeedbackOutcome, NetworkNode, NeuralComponent, NeuralComponentKind, CONTRACT_SCHEMA_VERSION,
};
