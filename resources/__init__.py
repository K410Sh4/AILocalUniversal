"""Adaptive resource estimation and model selection."""

from resources.estimator import ResourceEstimator
from resources.leases import (
    ModelLeaseConflict,
    ModelLifecycleLease,
    ModelLifecycleLeaseManager,
)
from resources.manager import AdaptiveResourceManager
from resources.residency import (
    ResidentCapacityAssessment,
    ResidentCapacityStatus,
)
from resources.selector import AdaptiveModelSelector, ModelSelectionResult
from resources.telemetry import (
    OllamaProcessMemorySnapshot,
    ProcessMemoryDelta,
    ProcessMemoryProbeStatus,
    compare_process_memory,
    probe_ollama_process_memory,
)

__all__ = [
    "AdaptiveModelSelector",
    "AdaptiveResourceManager",
    "ModelSelectionResult",
    "ModelLeaseConflict",
    "ModelLifecycleLease",
    "ModelLifecycleLeaseManager",
    "ResourceEstimator",
    "ResidentCapacityAssessment",
    "ResidentCapacityStatus",
    "OllamaProcessMemorySnapshot",
    "ProcessMemoryDelta",
    "ProcessMemoryProbeStatus",
    "compare_process_memory",
    "probe_ollama_process_memory",
]
