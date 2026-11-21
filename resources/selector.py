"""Seleção conservadora e explicável de modelos de chat."""

from __future__ import annotations

from dataclasses import dataclass

from engines.base import ModelInfo, RunningModelSnapshot
from engines.model_selector import ModelSelectionError
from model_hub.contracts import ModelRecord
from model_hub.hardware import HardwareProfile
from resources.contracts import (
    EstimateConfidence,
    ModelResourceEstimate,
    ResourcePlacement,
)
from resources.estimator import ResourceEstimator
from resources.profiles import ResourceProfile, normalize_resource_profile
from resources.residency import (
    ResidentCapacityAssessment,
    ResidentCapacityStatus,
    assess_resident_capacity,
)


@dataclass(frozen=True, slots=True)
class ModelSelectionResult:
    model: ModelInfo
    strategy: str
    explanation: str
    estimate: ModelResourceEstimate
    alternatives: tuple[str, ...] = ()
    residency_assessment: ResidentCapacityAssessment | None = None


class AdaptiveModelSelector:
    """Prefere candidatos com estimativa completa e memória suficiente.

    Quando os metadados não permitem estimar, mantém o comportamento legado
    de preferência/nome estável, mas identifica explicitamente o fallback.
    """

    def __init__(self, estimator: ResourceEstimator | None = None) -> None:
        self.estimator = estimator or ResourceEstimator()

    @staticmethod
    def _unknown_estimate(model_name: str, context_tokens: int) -> ModelResourceEstimate:
        return ModelResourceEstimate(
            model_id=f"ollama:{model_name.casefold()}",
            context_tokens=context_tokens,
            quantization=None,
            weight_bytes=None,
            kv_cache_bytes=None,
            runtime_overhead_bytes=0,
            total_required_bytes=None,
            placement=ResourcePlacement.UNKNOWN,
            confidence=EstimateConfidence.UNKNOWN,
            reasons=("Não há ficha local suficiente para estimar a memória.",),
        )

    @staticmethod
    def _resident_estimate(
        record: ModelRecord,
        context_tokens: int,
        assessment: ResidentCapacityAssessment,
    ) -> ModelResourceEstimate:
        return ModelResourceEstimate(
            model_id=record.record_id,
            context_tokens=context_tokens,
            quantization=None,
            weight_bytes=0,
            kv_cache_bytes=0,
            runtime_overhead_bytes=0,
            total_required_bytes=0,
            placement=ResourcePlacement.RESIDENT,
            confidence=EstimateConfidence.OBSERVED,
            reasons=(assessment.reason,),
        )

    def select(
        self,
        models: list[ModelInfo],
        records: dict[str, ModelRecord],
        hardware: HardwareProfile,
        *,
        preferred_model: str | None = None,
        context_tokens: int = 4096,
        task_category: str | None = None,
        resource_profile: str | ResourceProfile = ResourceProfile.MEDIUM,
        running_models: list[RunningModelSnapshot] | None = None,
        concurrent_requests: int = 1,
    ) -> ModelSelectionResult:
        if (
            isinstance(concurrent_requests, bool)
            or not isinstance(concurrent_requests, int)
            or concurrent_requests <= 0
        ):
            raise ValueError("concurrent_requests precisa ser um inteiro positivo.")
        selected_profile = normalize_resource_profile(resource_profile)
        profile_note = (
            f"Perfil de processamento: {selected_profile.value} "
            f"({selected_profile.usage_percent}%). "
        )
        candidates = [
            item for item in models
            if item.capabilities.verified and item.capabilities.chat
        ]
        if not candidates:
            raise ModelSelectionError(
                "Nenhum modelo de chat verificado está disponível no runtime."
            )

        evaluated: list[tuple[ModelInfo, ModelResourceEstimate, ModelRecord | None]] = []
        residency_assessments: dict[str, ResidentCapacityAssessment] = {}
        for model in candidates:
            record_id = f"ollama:{model.name.casefold()}"
            record = records.get(record_id)
            assessment = None
            if record is not None and running_models is not None:
                assessment = assess_resident_capacity(
                    record,
                    running_models,
                    context_tokens=context_tokens,
                    concurrent_requests=concurrent_requests,
                )
                residency_assessments[model.name] = assessment
            if (
                assessment is not None
                and assessment.status is ResidentCapacityStatus.REUSE_READY
                and record is not None
            ):
                estimate = self._resident_estimate(record, context_tokens, assessment)
            else:
                estimate = (
                    self.estimator.estimate(record, hardware, context_tokens=context_tokens)
                    if record is not None
                    else self._unknown_estimate(model.name, context_tokens)
                )
            evaluated.append((model, estimate, record))

        viable = [
            item for item in evaluated
            if item[1].total_required_bytes is not None
            and item[1].placement in {
                ResourcePlacement.GPU,
                ResourcePlacement.CPU,
                ResourcePlacement.HYBRID,
                ResourcePlacement.RESIDENT,
            }
        ]
        if viable:
            preferred = next(
                (item for item in viable if item[0].name == preferred_model),
                None,
            )
            if preferred is not None:
                chosen = preferred
                reason = (
                    "A preferência do usuário foi mantida; o runner residente "
                    "já comporta o contexto solicitado."
                    if preferred[1].placement is ResourcePlacement.RESIDENT
                    else "A preferência do usuário foi mantida porque a estimativa cabe."
                )
            else:
                placement_rank = {
                    ResourcePlacement.RESIDENT: 4,
                    ResourcePlacement.GPU: 3,
                    ResourcePlacement.HYBRID: 2,
                    ResourcePlacement.CPU: 1,
                }

                def rank(item):
                    model, estimate, record = item
                    category_match = int(
                        task_category is not None
                        and record is not None
                        and record.category == task_category
                    )
                    return (
                        -category_match,
                        -placement_rank[estimate.placement],
                        estimate.total_required_bytes or 0,
                        model.name.casefold(),
                    )

                chosen = sorted(viable, key=rank)[0]
                reason = (
                    "Runner já residente reutilizado: nenhuma nova alocação de "
                    "pesos/KV/buffers do runner é prevista."
                    if chosen[1].placement is ResourcePlacement.RESIDENT
                    else (
                        "Selecionado entre os candidatos cuja estimativa cabe nos recursos "
                        "disponíveis, priorizando a categoria da tarefa quando informada "
                        "e o posicionamento em GPU."
                    )
                )
            model, estimate, _record = chosen
            alternatives = tuple(
                item[0].name for item in viable if item[0].name != model.name
            )
            explanation = (
                profile_note
                + f"Seletor adaptativo: {model.name}; posicionamento sugerido="
                f"{estimate.placement.value}; contexto={context_tokens}; "
                f"memória estimada={estimate.total_required_bytes} bytes. {reason}"
            )
            return ModelSelectionResult(
                model=model,
                strategy=(
                    "resident_reuse"
                    if estimate.placement is ResourcePlacement.RESIDENT
                    else "adaptive"
                ),
                explanation=explanation,
                estimate=estimate,
                alternatives=alternatives,
                residency_assessment=residency_assessments.get(model.name),
            )

        unknown = [
            item for item in evaluated
            if item[1].placement is ResourcePlacement.UNKNOWN
            or (
                item[1].confidence in {
                    EstimateConfidence.PARTIAL,
                    EstimateConfidence.UNKNOWN,
                }
                and item[1].placement is not ResourcePlacement.DOES_NOT_FIT
            )
        ]
        if unknown:
            chosen = next(
                (item for item in unknown if item[0].name == preferred_model),
                None,
            )
            if chosen is None:
                chosen = sorted(unknown, key=lambda item: item[0].name.casefold())[0]
            model, estimate, _record = chosen
            explanation = (
                profile_note
                + f"Fallback conservador para {model.name}: não há metadados suficientes "
                "para garantir a memória de inferência. Nenhuma compatibilidade foi presumida."
            )
            return ModelSelectionResult(
                model=model,
                strategy="metadata_fallback",
                explanation=explanation,
                estimate=estimate,
                alternatives=tuple(
                    item[0].name for item in unknown if item[0].name != model.name
                ),
                residency_assessment=residency_assessments.get(model.name),
            )

        raise ModelSelectionError(
            "Nenhum modelo de chat cabe na estimativa conservadora de RAM/VRAM "
            f"para {context_tokens} tokens. Reduza o contexto ou escolha outro modelo."
        )
