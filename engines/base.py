"""Contrato comum para engines de inferência."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EngineCapabilities:
    """Capacidades declaradas por backend/modelo."""

    chat: bool = True
    streaming: bool = False
    vision: bool = False
    tool_calling: bool = False
    context_window: int | None = None
    embeddings: bool = False
    verified: bool = True


@dataclass(slots=True)
class ModelInfo:
    """Metadados normalizados de um modelo."""

    name: str
    size_bytes: int | None = None
    digest: str | None = None
    capabilities: EngineCapabilities = field(default_factory=EngineCapabilities)
    parameter_count: int | None = None
    architecture: str | None = None
    quantization: str | None = None
    context_window: int | None = None
    kv_cache_bytes_per_token: int | None = None


@dataclass(frozen=True, slots=True)
class RunningModelSnapshot:
    """Snapshot de residência reportado pelo backend, sem inferir RAM total."""

    name: str
    model: str | None = None
    digest: str | None = None
    size_bytes: int | None = None
    size_vram_bytes: int | None = None
    context_length: int | None = None
    expires_at: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("O nome do modelo residente não pode ser vazio.")
        for field_name in ("size_bytes", "size_vram_bytes"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{field_name} precisa ser inteiro não negativo ou None.")
        if self.context_length is not None and (
            isinstance(self.context_length, bool)
            or not isinstance(self.context_length, int)
            or self.context_length <= 0
        ):
            raise ValueError("context_length precisa ser inteiro positivo ou None.")


@dataclass(slots=True)
class EngineRequest:
    """Solicitação de chat independente de backend."""

    model: str
    messages: list[dict[str, Any]]
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EngineEvent:
    """Evento de streaming normalizado."""

    event_type: str
    content: str = ""
    done: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class EngineAdapter(ABC):
    """Interface que os adaptadores de inferência devem implementar."""

    name: str

    @abstractmethod
    async def health(self) -> bool:
        """Verifica se o backend está acessível."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Lista modelos disponíveis."""

    @abstractmethod
    async def stream_chat(self, request: EngineRequest) -> AsyncIterator[EngineEvent]:
        """Executa chat e emite eventos de streaming."""

    async def list_running_models(self) -> list[RunningModelSnapshot]:
        """Lista modelos residentes, quando o backend oferece essa telemetria."""
        return []

    async def close(self) -> None:
        """Libera recursos persistentes do adaptador, se existirem."""
        return None
