"""Perfis de orçamento de processamento com fallback explícito por backend."""

from __future__ import annotations

import math
from enum import StrEnum


class ResourceProfile(StrEnum):
    """Percentual-alvo de núcleos lógicos disponibilizados ao runtime."""

    LIGHT = "light"
    MEDIUM = "medium"
    ULTRA = "ultra"

    @property
    def usage_percent(self) -> int:
        return {
            ResourceProfile.LIGHT: 33,
            ResourceProfile.MEDIUM: 66,
            ResourceProfile.ULTRA: 95,
        }[self]


def normalize_resource_profile(value: str | ResourceProfile) -> ResourceProfile:
    """Normaliza um perfil persistido ou informa um valor inválido."""
    if isinstance(value, ResourceProfile):
        return value
    try:
        return ResourceProfile(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Perfil de processamento inválido; use light, medium ou ultra."
        ) from exc


def cpu_thread_budget(
    logical_cores: int | None,
    profile: str | ResourceProfile = ResourceProfile.MEDIUM,
) -> int | None:
    """Calcula threads aproximadas; não promete ocupação exata da CPU/GPU."""
    selected = normalize_resource_profile(profile)
    if logical_cores is None:
        return None
    if (
        isinstance(logical_cores, bool)
        or not isinstance(logical_cores, int)
        or logical_cores <= 0
    ):
        raise ValueError("logical_cores precisa ser inteiro positivo ou None.")
    return min(
        logical_cores,
        max(1, math.floor(logical_cores * selected.usage_percent / 100 + 0.5)),
    )
