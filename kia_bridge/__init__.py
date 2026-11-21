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

__all__ = [
    "HOST_PROTOCOL_VERSION",
    "KiaRuntimeClient",
    "KiaRuntimeError",
    "KiaRuntimeUnavailable",
    "build_network_payload",
    "capabilities_from_napa",
    "cognitive_request_from_napa",
    "components_from_model_records",
    "executor_ids_for_registered_engines",
    "host_state_payload",
    "resource_budget_from_profile",
    "resource_snapshot_from_hardware",
]
