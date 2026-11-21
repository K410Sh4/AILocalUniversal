"""Contratos para estimativas de memória e decisões adaptativas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResourcePlacement(StrEnum):
    """Estratégia de memória sugerida; não controla o runtime."""

    GPU = "gpu"
    CPU = "cpu"
    HYBRID = "hybrid"
    RESIDENT = "resident"
    DOES_NOT_FIT = "does_not_fit"
    UNKNOWN = "unknown"


class EstimateConfidence(StrEnum):
    """Completude dos metadados usados na estimativa."""

    OBSERVED = "observed"
    MEDIUM = "medium"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ModelResourceEstimate:
    """Estimativa explícita, com entradas, premissas e limitações auditáveis."""

    model_id: str
    context_tokens: int
    quantization: str | None
    weight_bytes: int | None
    kv_cache_bytes: int | None
    runtime_overhead_bytes: int
    total_required_bytes: int | None
    placement: ResourcePlacement
    confidence: EstimateConfidence
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id não pode ser vazio.")
        if (
            isinstance(self.context_tokens, bool)
            or not isinstance(self.context_tokens, int)
            or self.context_tokens <= 0
        ):
            raise ValueError("context_tokens precisa ser um inteiro positivo.")
        for name in (
            "weight_bytes",
            "kv_cache_bytes",
            "runtime_overhead_bytes",
            "total_required_bytes",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} precisa ser inteiro não negativo ou None.")
        if not self.reasons:
            raise ValueError("Toda estimativa precisa explicar suas premissas.")
