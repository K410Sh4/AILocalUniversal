"""Workers Qt que executam operações de engine fora da thread da UI."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

from PySide6.QtCore import QThread, Signal

from core.cognitive_task import CognitiveTask
from core.task_executor import CognitiveTaskExecutor
from engines.base import EngineAdapter, EngineRequest


class _AsyncWorker(QThread):
    """Executa coroutine em uma thread Qt e permite cancelamento cooperativo."""

    failed = Signal(str)
    cancelled = Signal()
    completed = Signal(object)

    def __init__(self, engine: EngineAdapter, parent=None) -> None:
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
        running_models = []
        residency_error = None
        if healthy:
            try:
                running_models = await self.engine.list_running_models()
            except Exception as exc:
                residency_error = str(exc)
        self.completed.emit(
            {
                "healthy": healthy,
                "models": models,
                "running_models": running_models,
                "residency_error": residency_error,
            }
        )


class OllamaChatWorker(_AsyncWorker):
    """Executa uma conversa e emite cada trecho recebido."""

    token = Signal(str)

    def __init__(self, engine: EngineAdapter, request: EngineRequest, parent=None) -> None:
        super().__init__(engine, parent)
        self.request = request

    async def execute(self) -> None:
        metadata: dict[str, Any] = {}
        async for event in self.engine.stream_chat(self.request):
            if event.content:
                self.token.emit(event.content)
            if event.done:
                metadata = event.metadata
        self.completed.emit(metadata)


class OllamaTaskExecutorWorker(_AsyncWorker):
    """Executa subtarefas em sequência e transmite somente a síntese final ao Chat."""

    token = Signal(str)
    progress = Signal(object)

    def __init__(
        self,
        engine: EngineAdapter,
        task: CognitiveTask,
        model: str,
        context_messages: list[dict[str, Any]],
        request_options: dict[str, Any],
        parent=None,
    ) -> None:
        super().__init__(engine, parent)
        self.task_data = copy.deepcopy(task.to_dict())
        self.model = model
        self.context_messages = copy.deepcopy(context_messages)
        self.request_options = copy.deepcopy(request_options)

    async def execute(self) -> None:
        task = CognitiveTask.from_dict(self.task_data)
        executor = CognitiveTaskExecutor(self.engine)
        metadata = await executor.execute(
            task,
            model=self.model,
            context_messages=self.context_messages,
            request_options=self.request_options,
            on_update=self.progress.emit,
            on_token=self.token.emit,
        )
        self.completed.emit({"task": task.to_dict(), "metadata": metadata})
