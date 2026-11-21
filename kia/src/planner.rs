use crate::{
    AdaptiveCognitiveNetwork, CapabilityId, CognitiveRequest, ComponentId, ResourceBudget,
    ResourceSnapshot, ResourceVector, RuntimeError,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PlannedComponent {
    pub component_id: ComponentId,
    pub capabilities: Vec<CapabilityId>,
    pub estimated_cost: ResourceVector,
    /// Score heurístico de roteamento, não probabilidade.
    pub routing_score: f32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExecutionPlan {
    pub request_id: String,
    pub network_version: u64,
    pub selections: Vec<PlannedComponent>,
    pub reserved_resources: ResourceVector,
}

fn tokenize(value: &str) -> BTreeSet<String> {
    value
        .split(|character: char| !character.is_alphanumeric())
        .filter(|token| !token.is_empty())
        .map(str::to_lowercase)
        .collect()
}

fn intent_affinity(request_intent: &str, tags: &BTreeSet<String>) -> f32 {
    if tags.is_empty() {
        return 0.0;
    }
    let intent = request_intent.trim().to_lowercase();
    let request_tokens = tokenize(request_intent);
    if tags.iter().any(|tag| {
        let normalized = tag.trim().to_lowercase();
        normalized == intent
            || tokenize(&normalized)
                .iter()
                .any(|token| request_tokens.contains(token))
    }) {
        1.0
    } else {
        0.0
    }
}

fn context_affinity(
    request_tags: &BTreeSet<String>,
    component_tags: &BTreeSet<String>,
    capability_tags: &BTreeSet<String>,
) -> f32 {
    if request_tags.is_empty() || (component_tags.is_empty() && capability_tags.is_empty()) {
        return 0.5;
    }
    let mut supported = component_tags.clone();
    supported.extend(capability_tags.iter().cloned());
    let matches = request_tags
        .iter()
        .filter(|tag| supported.contains(*tag))
        .count();
    matches as f32 / request_tags.len() as f32
}

fn score_component(
    network: &AdaptiveCognitiveNetwork,
    request: &CognitiveRequest,
    capability_id: &CapabilityId,
    component_id: &ComponentId,
) -> f32 {
    let capability = &network.capabilities()[capability_id];
    let component = &network.components()[component_id];
    let intent = intent_affinity(&request.intent, &capability.intent_tags);
    let context = context_affinity(
        &request.context_tags,
        &component.context_tags,
        &capability.context_tags,
    );
    let route_prior = network.support_weight(capability_id, component_id);
    (component.baseline_quality * 0.35 + route_prior * 0.40 + intent * 0.15 + context * 0.10)
        .clamp(0.0, 1.0)
}

pub fn build_plan<F>(
    network: &AdaptiveCognitiveNetwork,
    request: &CognitiveRequest,
    snapshot: &ResourceSnapshot,
    budget: &ResourceBudget,
    has_executor: F,
) -> Result<ExecutionPlan, RuntimeError>
where
    F: Fn(&ComponentId) -> bool,
{
    request.validate().map_err(RuntimeError::InvalidRequest)?;
    snapshot
        .validate()
        .map_err(RuntimeError::InvalidResources)?;
    if !budget.max.fits_within(&snapshot.available) {
        return Err(RuntimeError::BudgetExceedsAvailability);
    }

    let mut selections: Vec<PlannedComponent> = Vec::new();
    let mut reserved = ResourceVector::default();

    for capability_id in &request.required_capabilities {
        let capability = network
            .capabilities()
            .get(capability_id)
            .ok_or_else(|| RuntimeError::UnknownCapability(capability_id.clone()))?;
        if !capability.enabled {
            return Err(RuntimeError::NoEligibleComponent(capability_id.clone()));
        }

        let mut candidates: Vec<_> = network
            .components()
            .values()
            .filter(|component| {
                component.enabled
                    && component.resource_estimate_available
                    && component.supported_capabilities.contains(capability_id)
                    && has_executor(&component.id)
                    && snapshot.supports(component.execution_target)
            })
            .map(|component| {
                (
                    component.id.clone(),
                    score_component(network, request, capability_id, &component.id),
                    component.estimated_cost,
                )
            })
            .collect();
        candidates.sort_by(|left, right| {
            right
                .1
                .total_cmp(&left.1)
                .then_with(|| left.0.cmp(&right.0))
        });

        let mut chosen = false;
        for (component_id, routing_score, estimated_cost) in candidates {
            if let Some(existing) = selections
                .iter_mut()
                .find(|selection| selection.component_id == component_id)
            {
                existing.capabilities.push(capability_id.clone());
                existing.routing_score = existing.routing_score.max(routing_score);
                chosen = true;
                break;
            }

            if selections.len() >= request.max_components {
                break;
            }
            let Some(next_reserved) = reserved.checked_add(&estimated_cost) else {
                continue;
            };
            if !next_reserved.fits_within(&budget.max)
                || !estimated_cost.fits_within(&snapshot.available)
            {
                continue;
            }
            selections.push(PlannedComponent {
                component_id,
                capabilities: vec![capability_id.clone()],
                estimated_cost,
                routing_score,
            });
            reserved = next_reserved;
            chosen = true;
            break;
        }

        if !chosen {
            return Err(RuntimeError::NoEligibleComponent(capability_id.clone()));
        }
    }

    Ok(ExecutionPlan {
        request_id: request.request_id.clone(),
        network_version: network.version(),
        selections,
        reserved_resources: reserved,
    })
}

/// Planeja usando IDs de executores conhecidos pelo processo da aplicação.
pub fn plan_with_executor_ids(
    network: &AdaptiveCognitiveNetwork,
    request: &CognitiveRequest,
    snapshot: &ResourceSnapshot,
    budget: &ResourceBudget,
    available_executors: &BTreeSet<ComponentId>,
) -> Result<ExecutionPlan, RuntimeError> {
    build_plan(network, request, snapshot, budget, |component_id| {
        available_executors.contains(component_id)
    })
}
