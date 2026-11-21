"""Integração Python do K.BA Runtime Host."""

from kba_bridge.adapters import (
    build_network_payload,
    capabilities_from_napa,
    cognitive_request_from_napa,
    components_from_model_records,
    executor_ids_for_registered_engines,
    host_state_payload,
    resource_budget_from_profile,
    resource_snapshot_from_hardware,
)
from kba_bridge.client import (
    HOST_PROTOCOL_VERSION,
    KbaRuntimeClient,
    KbaRuntimeError,
    KbaRuntimeUnavailable,
)
from kba_bridge.flow import (
    KbaExecutionCoordinator,
    KbaFlowError,
    KbaPlanDecision,
    append_kba_plan_to_task,
    execute_deterministic_selection,
    record_validated_deterministic_feedback,
)
from kba_bridge.memory import (
    KbaMemoryError,
    KbaMemoryStore,
    default_kba_memory_path,
)

__all__ = [
    "HOST_PROTOCOL_VERSION",
    "KbaExecutionCoordinator",
    "KbaMemoryError",
    "KbaMemoryStore",
    "KbaFlowError",
    "KbaPlanDecision",
    "KbaRuntimeClient",
    "KbaRuntimeError",
    "KbaRuntimeUnavailable",
    "append_kba_plan_to_task",
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
    "default_kba_memory_path",
]
