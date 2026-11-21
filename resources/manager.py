"""Orquestra snapshot de hardware, estimativas e seleção adaptativa."""

from __future__ import annotations

from engines.base import ModelInfo
from model_hub.hardware import HardwareProfile, HardwareProfiler
from model_hub.registry import ModelRegistry
from resources.contracts import ModelResourceEstimate
from resources.estimator import ResourceEstimator
from resources.selector import AdaptiveModelSelector, ModelSelectionResult


class AdaptiveResourceManager:
    """Serviço local de consulta; não altera processos ou configurações do runtime."""

    def __init__(
        self,
        hardware_profiler: HardwareProfiler | None = None,
        estimator: ResourceEstimator | None = None,
        selector: AdaptiveModelSelector | None = None,
    ) -> None:
        self.hardware_profiler = hardware_profiler or HardwareProfiler()
        self.estimator = estimator or ResourceEstimator()
        self.selector = selector or AdaptiveModelSelector(self.estimator)

    def snapshot(self) -> HardwareProfile:
        """Retorna uma nova fotografia de CPU/RAM/disco/GPU."""
        return self.hardware_profiler.probe()

    def estimate_model(
        self,
        model_id: str,
        registry: ModelRegistry,
        *,
        context_tokens: int = 4096,
        hardware: HardwareProfile | None = None,
    ) -> ModelResourceEstimate:
        record = registry.get(model_id)
        if record is None:
            raise KeyError(f"Modelo não encontrado no registro: {model_id}")
        return self.estimator.estimate(
            record,
            hardware or self.snapshot(),
            context_tokens=context_tokens,
        )

    def select_chat_model(
        self,
        models: list[ModelInfo],
        registry: ModelRegistry,
        *,
        preferred_model: str | None = None,
        context_tokens: int = 4096,
        task_category: str | None = None,
        hardware: HardwareProfile | None = None,
    ) -> ModelSelectionResult:
        profile = hardware or self.snapshot()
        records = {
            record.record_id: record
            for record in registry.list_records()
        }
        return self.selector.select(
            models,
            records,
            profile,
            preferred_model=preferred_model,
            context_tokens=context_tokens,
            task_category=task_category,
        )
