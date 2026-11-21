use crate::{
    CapabilityId, CognitiveConnection, CognitiveFeedback, ComponentId, ConnectionKind,
    FeedbackOutcome, NetworkNode, NeuralComponent,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fmt::{Display, Formatter};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct AdaptiveCognitiveNetwork {
    capabilities: BTreeMap<CapabilityId, crate::CognitiveCapability>,
    components: BTreeMap<ComponentId, NeuralComponent>,
    connections: Vec<CognitiveConnection>,
    feedback_history: Vec<CognitiveFeedback>,
    version: u64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum NetworkError {
    DuplicateCapability(CapabilityId),
    DuplicateComponent(ComponentId),
    UnknownCapability(CapabilityId),
    UnknownComponent(ComponentId),
    InvalidCapability(String),
    InvalidComponent(String),
    InvalidConnection(String),
    InvalidFeedback(String),
    InvalidLearningRate,
    InvalidNetwork(String),
}

impl Display for NetworkError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for NetworkError {}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PlasticityUpdate {
    pub previous_weight: f32,
    pub updated_weight: f32,
    pub observations: u64,
}

impl AdaptiveCognitiveNetwork {
    pub fn version(&self) -> u64 {
        self.version
    }

    pub fn capabilities(&self) -> &BTreeMap<CapabilityId, crate::CognitiveCapability> {
        &self.capabilities
    }

    pub fn components(&self) -> &BTreeMap<ComponentId, NeuralComponent> {
        &self.components
    }

    pub fn connections(&self) -> &[CognitiveConnection] {
        &self.connections
    }

    pub fn feedback_history(&self) -> &[CognitiveFeedback] {
        &self.feedback_history
    }

    pub fn add_capability(
        &mut self,
        capability: crate::CognitiveCapability,
    ) -> Result<(), NetworkError> {
        if !capability.id.is_valid()
            || capability.name.trim().is_empty()
            || capability.domain.trim().is_empty()
        {
            return Err(NetworkError::InvalidCapability(
                "ID, nome e domínio da capacidade precisam ser válidos.".to_owned(),
            ));
        }
        let id = capability.id.clone();
        if self.capabilities.contains_key(&id) {
            return Err(NetworkError::DuplicateCapability(id));
        }
        self.capabilities.insert(id, capability);
        self.version += 1;
        Ok(())
    }

    pub fn add_component(&mut self, component: NeuralComponent) -> Result<(), NetworkError> {
        if !component.id.is_valid()
            || component.name.trim().is_empty()
            || !component.baseline_quality.is_finite()
            || !(0.0..=1.0).contains(&component.baseline_quality)
            || component.supported_capabilities.is_empty()
        {
            return Err(NetworkError::InvalidComponent(
                "ID, nome, score e capacidades do componente são inválidos.".to_owned(),
            ));
        }
        for capability_id in &component.supported_capabilities {
            if !self.capabilities.contains_key(capability_id) {
                return Err(NetworkError::UnknownCapability(capability_id.clone()));
            }
        }
        let id = component.id.clone();
        if self.components.contains_key(&id) {
            return Err(NetworkError::DuplicateComponent(id));
        }
        self.components.insert(id, component);
        self.version += 1;
        Ok(())
    }

    pub fn add_connection(&mut self, connection: CognitiveConnection) -> Result<(), NetworkError> {
        self.validate_node(&connection.from)?;
        self.validate_node(&connection.to)?;
        if !connection.weight.is_finite()
            || !(0.0..=1.0).contains(&connection.weight)
            || connection.successes > connection.observations
        {
            return Err(NetworkError::InvalidConnection(
                "Peso ou contadores da conexão são inválidos.".to_owned(),
            ));
        }
        if connection.from == connection.to {
            return Err(NetworkError::InvalidConnection(
                "Uma conexão não pode apontar para o próprio nó.".to_owned(),
            ));
        }
        if connection.kind == ConnectionKind::Supports {
            match (&connection.from, &connection.to) {
                (NetworkNode::Capability(capability), NetworkNode::Component(component)) => {
                    let node = self
                        .components
                        .get(component)
                        .ok_or_else(|| NetworkError::UnknownComponent(component.clone()))?;
                    if !node.supported_capabilities.contains(capability) {
                        return Err(NetworkError::InvalidConnection(
                            "O componente não declara suporte à capacidade de origem.".to_owned(),
                        ));
                    }
                }
                _ => {
                    return Err(NetworkError::InvalidConnection(
                        "Supports deve conectar Capability -> Component.".to_owned(),
                    ));
                }
            }
        }
        if self.connections.iter().any(|existing| {
            existing.from == connection.from
                && existing.to == connection.to
                && existing.kind == connection.kind
        }) {
            return Err(NetworkError::InvalidConnection(
                "A conexão tipada já existe.".to_owned(),
            ));
        }
        self.connections.push(connection);
        self.version += 1;
        Ok(())
    }

    fn validate_node(&self, node: &NetworkNode) -> Result<(), NetworkError> {
        match node {
            NetworkNode::Capability(id) if !self.capabilities.contains_key(id) => {
                Err(NetworkError::UnknownCapability(id.clone()))
            }
            NetworkNode::Component(id) if !self.components.contains_key(id) => {
                Err(NetworkError::UnknownComponent(id.clone()))
            }
            _ => Ok(()),
        }
    }

    /// Valida também redes desserializadas de fontes externas.
    pub fn validate(&self) -> Result<(), NetworkError> {
        for (id, capability) in &self.capabilities {
            if !id.is_valid()
                || id != &capability.id
                || capability.name.trim().is_empty()
                || capability.domain.trim().is_empty()
            {
                return Err(NetworkError::InvalidNetwork(
                    "Registro de capacidade inconsistente.".to_owned(),
                ));
            }
        }
        for (id, component) in &self.components {
            if !id.is_valid()
                || id != &component.id
                || component.name.trim().is_empty()
                || !component.baseline_quality.is_finite()
                || !(0.0..=1.0).contains(&component.baseline_quality)
                || component.supported_capabilities.is_empty()
                || component
                    .supported_capabilities
                    .iter()
                    .any(|capability| !self.capabilities.contains_key(capability))
            {
                return Err(NetworkError::InvalidNetwork(
                    "Registro de componente inconsistente ou com capacidade ausente.".to_owned(),
                ));
            }
        }
        for (index, connection) in self.connections.iter().enumerate() {
            self.validate_node(&connection.from)?;
            self.validate_node(&connection.to)?;
            if !connection.weight.is_finite()
                || !(0.0..=1.0).contains(&connection.weight)
                || connection.successes > connection.observations
                || connection.from == connection.to
            {
                return Err(NetworkError::InvalidNetwork(
                    "Conexão com peso, contador ou extremidade inválida.".to_owned(),
                ));
            }
            if connection.kind == ConnectionKind::Supports {
                match (&connection.from, &connection.to) {
                    (NetworkNode::Capability(capability), NetworkNode::Component(component)) => {
                        if !self.components[component]
                            .supported_capabilities
                            .contains(capability)
                        {
                            return Err(NetworkError::InvalidNetwork(
                                "Conexão Supports contradiz as capacidades do componente."
                                    .to_owned(),
                            ));
                        }
                    }
                    _ => {
                        return Err(NetworkError::InvalidNetwork(
                            "Conexão Supports precisa ser Capability -> Component.".to_owned(),
                        ));
                    }
                }
            }
            if self.connections[..index].iter().any(|previous| {
                previous.from == connection.from
                    && previous.to == connection.to
                    && previous.kind == connection.kind
            }) {
                return Err(NetworkError::InvalidNetwork(
                    "Conexão tipada duplicada.".to_owned(),
                ));
            }
        }
        for feedback in &self.feedback_history {
            let component = self.components.get(&feedback.component_id);
            let component_supports_capability = component.is_some_and(|item| {
                item.supported_capabilities
                    .contains(&feedback.capability_id)
            });
            if !self.capabilities.contains_key(&feedback.capability_id)
                || !component_supports_capability
                || feedback.validation_ref.trim().is_empty()
            {
                return Err(NetworkError::InvalidNetwork(
                    "Histórico de feedback contém referência inválida.".to_owned(),
                ));
            }
        }
        Ok(())
    }

    pub fn support_weight(&self, capability_id: &CapabilityId, component_id: &ComponentId) -> f32 {
        self.connections
            .iter()
            .find(|connection| {
                connection.kind == ConnectionKind::Supports
                    && connection.from == NetworkNode::Capability(capability_id.clone())
                    && connection.to == NetworkNode::Component(component_id.clone())
            })
            .map(|connection| connection.weight)
            .unwrap_or(0.5)
    }

    pub fn record_evaluated_feedback(
        &mut self,
        feedback: CognitiveFeedback,
        learning_rate: f32,
    ) -> Result<PlasticityUpdate, NetworkError> {
        if !learning_rate.is_finite() || learning_rate <= 0.0 || learning_rate > 1.0 {
            return Err(NetworkError::InvalidLearningRate);
        }
        if feedback.validation_ref.trim().is_empty() {
            return Err(NetworkError::InvalidFeedback(
                "O feedback precisa referenciar uma avaliação independente.".to_owned(),
            ));
        }
        let capability = self
            .capabilities
            .get(&feedback.capability_id)
            .ok_or_else(|| NetworkError::UnknownCapability(feedback.capability_id.clone()))?;
        let component = self
            .components
            .get(&feedback.component_id)
            .ok_or_else(|| NetworkError::UnknownComponent(feedback.component_id.clone()))?;
        if !component
            .supported_capabilities
            .contains(&feedback.capability_id)
        {
            return Err(NetworkError::InvalidFeedback(
                "O componente não está associado à capacidade avaliada.".to_owned(),
            ));
        }
        if !capability.enabled || !component.enabled {
            return Err(NetworkError::InvalidFeedback(
                "Não é permitido atualizar uma rota desativada.".to_owned(),
            ));
        }

        let capability_id = feedback.capability_id.clone();
        let component_id = feedback.component_id.clone();
        let from = NetworkNode::Capability(capability_id.clone());
        let to = NetworkNode::Component(component_id.clone());
        let position = self.connections.iter().position(|connection| {
            connection.kind == ConnectionKind::Supports
                && connection.from == from
                && connection.to == to
        });
        let previous_weight = position
            .map(|index| self.connections[index].weight)
            .unwrap_or(0.5);
        let updated_weight = (previous_weight
            + learning_rate * (feedback.outcome.target() - previous_weight))
            .clamp(0.0, 1.0);

        if let Some(index) = position {
            let connection = &mut self.connections[index];
            connection.weight = updated_weight;
            connection.observations += 1;
            if feedback.outcome == FeedbackOutcome::Success {
                connection.successes += 1;
            }
        } else {
            self.connections.push(CognitiveConnection {
                from,
                to,
                kind: ConnectionKind::Supports,
                weight: updated_weight,
                observations: 1,
                successes: if feedback.outcome == FeedbackOutcome::Success {
                    1
                } else {
                    0
                },
            });
        }
        self.feedback_history.push(feedback);
        self.version += 1;
        let observations = self
            .connections
            .iter()
            .find(|connection| {
                connection.kind == ConnectionKind::Supports
                    && connection.from == NetworkNode::Capability(capability_id.clone())
                    && connection.to == NetworkNode::Component(component_id.clone())
            })
            .map(|connection| connection.observations)
            .unwrap_or(0);
        Ok(PlasticityUpdate {
            previous_weight,
            updated_weight,
            observations,
        })
    }
}
