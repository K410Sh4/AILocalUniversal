"""Estimador conservador de memória de inferência.

O tamanho do artefato em disco nunca é convertido diretamente em RAM/VRAM.
"""

from __future__ import annotations

import math
import re

from model_hub.contracts import ModelRecord
from model_hub.hardware import HardwareProfile
from resources.contracts import (
    EstimateConfidence,
    ModelResourceEstimate,
    ResourcePlacement,
)

MIB = 1024**2
DEFAULT_RUNTIME_OVERHEAD_BYTES = 768 * MIB
DEFAULT_SAFETY_FACTOR = 1.12
DEFAULT_MEMORY_RESERVE = 0.15

# Bits médios aproximados por parâmetro, incluindo escalas/metadados típicos.
# São coeficientes de planejamento, não tamanhos exatos de arquivos GGUF.
_QUANTIZATION_BITS = {
    "q4_k_m": 4.8,
    "q4_k_s": 4.6,
    "q4_0": 4.5,
    "q4_1": 5.0,
    "q5_k_m": 5.7,
    "q5_k_s": 5.5,
    "q5_0": 5.5,
    "q5_1": 6.0,
    "q6_k": 6.6,
    "q8_0": 8.5,
    "f16": 16.0,
    "fp16": 16.0,
    "bf16": 16.0,
    "f32": 32.0,
    "fp32": 32.0,
}


def _normalize_quantization(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^a-z0-9_]", "", value.casefold())
    return normalized or None


def _artifact_quantization(model: ModelRecord) -> str | None:
    artifacts = sorted(
        model.artifacts,
        key=lambda item: (not item.installed, item.runtime != "ollama"),
    )
    for artifact in artifacts:
        value = artifact.quantization
        if value:
            return value
        match = re.search(r"(q[4568]_[a-z0-9_]+|f16|fp16|bf16|f32|fp32)", artifact.reference, re.I)
        if match:
            return match.group(1)
    return None


class ResourceEstimator:
    """Estima pesos + cache KV + reserva de runtime, sem usar tamanho em disco.

    O modelo precisa possuir contagem total de parâmetros, quantização conhecida
    e custo de cache KV por token derivado de metadados arquiteturais disponíveis.
    Para MoE, usa parâmetros totais para estimar os pesos, nunca parâmetros ativos.
    """

    def __init__(
        self,
        *,
        runtime_overhead_bytes: int = DEFAULT_RUNTIME_OVERHEAD_BYTES,
        safety_factor: float = DEFAULT_SAFETY_FACTOR,
        memory_reserve: float = DEFAULT_MEMORY_RESERVE,
    ) -> None:
        if runtime_overhead_bytes < 0:
            raise ValueError("runtime_overhead_bytes não pode ser negativo.")
        if not 1.0 <= safety_factor <= 2.0:
            raise ValueError("safety_factor deve estar entre 1.0 e 2.0.")
        if not 0.0 <= memory_reserve < 0.5:
            raise ValueError("memory_reserve deve estar entre 0 e 0.5.")
        self.runtime_overhead_bytes = runtime_overhead_bytes
        self.safety_factor = safety_factor
        self.memory_reserve = memory_reserve

    def estimate(
        self,
        model: ModelRecord,
        hardware: HardwareProfile,
        *,
        context_tokens: int = 4096,
    ) -> ModelResourceEstimate:
        if isinstance(context_tokens, bool) or context_tokens <= 0:
            raise ValueError("context_tokens precisa ser um inteiro positivo.")

        reasons: list[str] = []
        quantization = _normalize_quantization(_artifact_quantization(model))
        bits_per_parameter = (
            _QUANTIZATION_BITS.get(quantization) if quantization is not None else None
        )

        if model.context_window is not None and context_tokens > model.context_window:
            return ModelResourceEstimate(
                model_id=model.record_id,
                context_tokens=context_tokens,
                quantization=quantization,
                weight_bytes=None,
                kv_cache_bytes=None,
                runtime_overhead_bytes=self.runtime_overhead_bytes,
                total_required_bytes=None,
                placement=ResourcePlacement.DOES_NOT_FIT,
                confidence=EstimateConfidence.MEDIUM,
                reasons=(
                    f"Contexto solicitado ({context_tokens}) excede a janela declarada "
                    f"({model.context_window}).",
                ),
            )

        if model.parameter_count is None or bits_per_parameter is None:
            missing = []
            if model.parameter_count is None:
                missing.append("contagem total de parâmetros")
            if bits_per_parameter is None:
                missing.append("quantização reconhecida")
            return ModelResourceEstimate(
                model_id=model.record_id,
                context_tokens=context_tokens,
                quantization=quantization,
                weight_bytes=None,
                kv_cache_bytes=None,
                runtime_overhead_bytes=self.runtime_overhead_bytes,
                total_required_bytes=None,
                placement=ResourcePlacement.UNKNOWN,
                confidence=EstimateConfidence.UNKNOWN,
                reasons=(
                    "Estimativa bloqueada: faltam " + " e ".join(missing) + ".",
                    "O tamanho do artefato em disco não substitui esses metadados.",
                ),
            )

        weight_bytes = math.ceil(
            model.parameter_count * bits_per_parameter / 8 * self.safety_factor
        )
        reasons.append(
            "Pesos estimados por parâmetros totais × bits médios da quantização, "
            f"com margem de {self.safety_factor:.0%}."
        )

        kv_bytes_per_token = model.kv_cache_bytes_per_token
        gpu_values = [
            item.vram_available_bytes
            for item in hardware.accelerators
            if item.vram_available_bytes is not None and item.vram_available_bytes > 0
        ]
        gpu_available = max(gpu_values) if gpu_values else None
        ram_available = hardware.ram_available_bytes

        gpu_usable = (
            int(gpu_available * (1 - self.memory_reserve))
            if gpu_available is not None
            else None
        )
        ram_usable = (
            int(ram_available * (1 - self.memory_reserve))
            if ram_available is not None
            else None
        )

        gpu_usable = (
            int(gpu_available * (1 - self.memory_reserve))
            if gpu_available is not None
            else None
        )
        ram_usable = (
            int(ram_available * (1 - self.memory_reserve))
            if ram_available is not None
            else None
        )

        if kv_bytes_per_token is None:
            lower_bound = weight_bytes + self.runtime_overhead_bytes
            reasons.append(
                "Cache KV não estimado: faltam metadados arquiteturais suficientes."
            )
            reasons.append(
                f"Limite inferior conhecido (pesos + runtime): {lower_bound} bytes."
            )
            if (
                gpu_usable is not None
                and ram_usable is not None
                and lower_bound > gpu_usable + ram_usable
            ) or (
                gpu_usable is None
                and ram_usable is not None
                and lower_bound > ram_usable
            ) or (
                ram_usable is None
                and gpu_usable is not None
                and lower_bound > gpu_usable
            ):
                placement = ResourcePlacement.DOES_NOT_FIT
                reasons.append(
                    "Mesmo sem contabilizar o cache KV, o limite inferior excede "
                    "a memória utilizável observada."
                )
            else:
                placement = ResourcePlacement.UNKNOWN
                reasons.append("A decisão de compatibilidade permanece inconclusiva.")
            return ModelResourceEstimate(
                model_id=model.record_id,
                context_tokens=context_tokens,
                quantization=quantization,
                weight_bytes=weight_bytes,
                kv_cache_bytes=None,
                runtime_overhead_bytes=self.runtime_overhead_bytes,
                total_required_bytes=None,
                placement=placement,
                confidence=EstimateConfidence.PARTIAL,
                reasons=tuple(reasons),
            )

        kv_cache_bytes = kv_bytes_per_token * context_tokens
        total_required_bytes = weight_bytes + kv_cache_bytes + self.runtime_overhead_bytes
        reasons.extend(
            (
                f"Cache KV calculado em {kv_bytes_per_token} bytes/token × "
                f"{context_tokens} tokens.",
                f"Reserva fixa de runtime: {self.runtime_overhead_bytes} bytes.",
                "O custo estimado não inclui cargas externas, concorrência ou "
                "particularidades não expostas pelo runtime.",
            )
        )

        if gpu_usable is not None and total_required_bytes <= gpu_usable:
            placement = ResourcePlacement.GPU
            reasons.append("A estimativa cabe na VRAM medida após a margem de segurança.")
        elif (
            gpu_usable is not None
            and ram_usable is not None
            and total_required_bytes <= gpu_usable + ram_usable
        ):
            placement = ResourcePlacement.HYBRID
            reasons.append(
                "A soma conservadora de RAM e VRAM comporta a estimativa; "
                "a execução híbrida depende do offload suportado pelo runtime."
            )
        elif ram_usable is not None and total_required_bytes <= ram_usable:
            placement = ResourcePlacement.CPU
            reasons.append("A estimativa cabe na RAM disponível após a margem de segurança.")
        elif gpu_usable is not None or ram_usable is not None:
            placement = ResourcePlacement.DOES_NOT_FIT
            reasons.append(
                "A estimativa excede a memória utilizável observada com a margem definida."
            )
        else:
            placement = ResourcePlacement.UNKNOWN
            reasons.append("RAM/VRAM disponível não pôde ser medida.")

        reasons.append(
            "Estimativa teórica de confiança média; não é garantia de carregamento "
            "nem substitui medição real do Ollama."
        )
        return ModelResourceEstimate(
            model_id=model.record_id,
            context_tokens=context_tokens,
            quantization=quantization,
            weight_bytes=weight_bytes,
            kv_cache_bytes=kv_cache_bytes,
            runtime_overhead_bytes=self.runtime_overhead_bytes,
            total_required_bytes=total_required_bytes,
            placement=placement,
            confidence=EstimateConfidence.MEDIUM,
            reasons=tuple(reasons),
        )
