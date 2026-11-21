"""Orquestra snapshot de hardware, estimativas e seleção adaptativa."""

from __future__ import annotations

from engines.base import ModelInfo, RunningModelSnapshot
from model_hub.hardware import HardwareProfile, HardwareProfiler
from model_hub.registry import ModelRegistry
from resources.contracts import ModelResourceEstimate
from resources.estimator import ResourceEstimator
from resources.profiles import (
    ResourceProfile,
    cpu_thread_budget,
    normalize_resource_profile,
)
from resources.residency import (\n    ModelResidency,\n    ResidentCapacityAssessment,\n    assess_resident_capacity,\n    reconcile_model_residency,\n)
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

    def cpu_thread_limit(
        self,
        resource_profile: str | ResourceProfile = ResourceProfile.MEDIUM,
        *,
        hardware: HardwareProfile | None = None,
    ) -> int | None:
        """Retorna o limite aproximado de threads para o perfil selecionado."""
        selected_hardware = hardware or self.snapshot()
        return cpu_thread_budget(
            selected_hardware.cpu_logical_cores,
            normalize_resource_profile(resource_profile),
        )

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

    def reconcile_residency(
        self,
        model_id: str,
        registry: ModelRegistry,
        snapshots: list[RunningModelSnapshot],
        *,
        runtime: str = "ollama",
    ) -> ModelResidency:
        """Confirma identidade residente sem alterar a estimativa de memória."""
        record = registry.get(model_id)
        if record is None:
            raise KeyError(f"Modelo não encontrado no registro: {model_id}")
        return reconcile_model_residency(record, snapshots, runtime=runtime)

    def select_chat_model(
        self,
        models: list[ModelInfo],
        registry: ModelRegistry,
        *,
        preferred_model: str | None = None,
        context_tokens: int = 4096,
        task_category: str | None = None,
        hardware: HardwareProfile | None = None,
        resource_profile: str | ResourceProfile = ResourceProfile.MEDIUM,
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
            resource_profile=normalize_resource_profile(resource_profile),
        )
