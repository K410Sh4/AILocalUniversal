"""Avaliação conservadora da compatibilidade entre modelo e hardware."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from model_hub.contracts import ModelRecord
from model_hub.hardware import HardwareProfile


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    status: CompatibilityStatus
    reasons: tuple[str, ...]
    evidence_url: str | None = None


class CompatibilityEngine:
    """Só declara compatibilidade quando há requisitos verificados.

    Artefato em disco não é tratado como tamanho de memória de execução.
    """

    def assess(
        self,
        model: ModelRecord,
        hardware: HardwareProfile,
        *,
        available_runtimes: set[str] | None = None,
    ) -> CompatibilityResult:
        installed = [item for item in model.artifacts if item.installed]
        reasons = [] if installed else [
            "Nenhum artefato instalado foi observado para este modelo."
        ]
        if available_runtimes is not None:
            runtimes = {item.runtime for item in installed}
            if runtimes and not runtimes.intersection(available_runtimes):
                return CompatibilityResult(
                    CompatibilityStatus.INCOMPATIBLE,
                    ("O runtime do artefato não está disponível neste ambiente.",),
                )
            if not runtimes and not available_runtimes:
                reasons.append("Nenhum runtime foi confirmado como disponível.")

        requirements = model.resource_requirements
        if requirements is None or not requirements.verified:
            reasons.append(
                "Requisitos de RAM/VRAM não verificados; tamanho do arquivo não estima "
                "memória de inferência."
            )
            return CompatibilityResult(CompatibilityStatus.UNKNOWN, tuple(reasons))

        checks = 0
        if requirements.minimum_ram_bytes is not None:
            if hardware.ram_available_bytes is None:
                reasons.append("Memória RAM disponível não pôde ser medida.")
            else:
                checks += 1
                if requirements.minimum_ram_bytes > hardware.ram_available_bytes:
                    return CompatibilityResult(
                        CompatibilityStatus.INCOMPATIBLE,
                        ("RAM disponível inferior ao requisito mínimo verificado.",),
                        requirements.evidence_url,
                    )

        if requirements.minimum_vram_bytes is not None:
            values = [
                item.vram_available_bytes
                for item in hardware.accelerators
                if item.vram_available_bytes is not None
            ]
            if not values:
                return CompatibilityResult(
                    CompatibilityStatus.INCOMPATIBLE,
                    (
                        "O modelo exige VRAM mínima verificada, mas nenhuma VRAM "
                        "disponível foi detectada.",
                    ),
                    requirements.evidence_url,
                )
            checks += 1
            if requirements.minimum_vram_bytes > max(values):
                return CompatibilityResult(
                    CompatibilityStatus.INCOMPATIBLE,
                    ("VRAM disponível inferior ao requisito mínimo verificado.",),
                    requirements.evidence_url,
                )

        if checks == 0:
            reasons.append("O catálogo não contém limites mínimos de memória suficientes.")
            return CompatibilityResult(CompatibilityStatus.UNKNOWN, tuple(reasons))
        reasons.append("Os requisitos mínimos verificados cabem nos recursos medidos.")
        if not installed:
            reasons.append("Compatibilidade de recursos não significa que o runtime esteja instalado.")
        return CompatibilityResult(
            CompatibilityStatus.COMPATIBLE, tuple(reasons), requirements.evidence_url
        )
