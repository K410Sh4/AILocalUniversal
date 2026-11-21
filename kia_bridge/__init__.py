"""Integração Python do K.IA Runtime Host."""

from kia_bridge.adapters import (
    build_network_payload,
    capabilities_from_napa,
    cognitive_request_from_napa,
    components_from_model_records,
    executor_ids_for_registered_engines,
    host_state_payload,
    resource_budget_from_profile,
    resource_snapshot_from_hardware,
)
from kia_bridge.client import (
    HOST_PROTOCOL_VERSION,
    KiaRuntimeClient,
    KiaRuntimeError,
    KiaRuntimeUnavailable,
)
from kia_bridge.flow import (
    KiaExecutionCoordinator,
    KiaFlowError,
    KiaPlanDecision,
    append_kia_plan_to_task,
    execute_deterministic_selection,
    record_validated_deterministic_feedback,
)

__all__ = [
    "HOST_PROTOCOL_VERSION",
    "KiaExecutionCoordinator",
    "KiaFlowError",
    "KiaPlanDecision",
    "KiaRuntimeClient",
    "KiaRuntimeError",
    "KiaRuntimeUnavailable",
    "append_kia_plan_to_task",
    "build_network_payload",
    "capabilities_from_napa",
    "cognitive_request_from_napa",
    "components_from_model_records",
    "execute_deterministic_selection",
    "executor_ids_for_registered_engines",
    "host_state_payload",
    "record_validated_deterministic_feedback",
    "resource_budget_from_profile",
    "resource_snapshot_from_hardware",
]
