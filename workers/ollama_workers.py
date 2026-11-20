"""Workers Qt que executam operações Ollama em event loop próprio."""

from __future__ import annotations

import asyncio
from typing import Any

from PySide6.QtCore import QThread, Signal

from engines.base import EngineRequest
from engines.ollama_engine import OllamaEngine


class _AsyncWorker(QThread):
    """Executa coroutine em uma thread Qt e permite cancelamento seguro."""

    failed = Signal(str)
    cancelled = Signal()
    completed = Signal(object)

    def __init__(self, engine: OllamaEngine, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[Any] | None = None

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._task = loop.create_task(self.execute())
        try:
            loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            self._task = None
            self._loop = None
            asyncio.set_event_loop(None)

    async def execute(self) -> None:
        raise NotImplementedError

    def cancel(self) -> None:
        """Solicita cancelamento sem bloquear a interface."""
        loop, task = self._loop, self._task
        if loop is not None and task is not None and not task.done():
            loop.call_soon_threadsafe(task.cancel)


class OllamaStatusWorker(_AsyncWorker):
    """Consulta saúde do backend e inventário de modelos."""

    async def execute(self) -> None:
        healthy = await self.engine.health()
        models = await self.engine.list_models() if healthy else []
        self.completed.emit({"healthy": healthy, "models": models})


class OllamaChatWorker(_AsyncWorker):
    """Executa uma conversa e emite cada trecho recebido."""

    token = Signal(str)
    generation_completed = Signal(object)

    def __init__(self, engine: OllamaEngine, request: EngineRequest, parent=None) -> None:
        super().__init__(engine, parent)
        self.request = request

    async def execute(self) -> None:
        metadata: dict[str, Any] = {}
        async for event in self.engine.stream_chat(self.request):
            if event.content:
                self.token.emit(event.content)
            if event.done:
                metadata = event.metadata
        self.generation_completed.emit(metadata)
        self.completed.emit(metadata)
