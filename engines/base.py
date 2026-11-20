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


@dataclass(slots=True)
class ModelInfo:
    """Metadados normalizados de um modelo."""

    name: str
    size_bytes: int | None = None
    digest: str | None = None
    capabilities: EngineCapabilities = field(default_factory=EngineCapabilities)


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

    async def close(self) -> None:
        """Libera recursos persistentes do adaptador, se existirem."""
