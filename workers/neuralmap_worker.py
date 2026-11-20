"""QThread worker for asynchronous NeuralMap graph execution."""

from __future__ import annotations

import asyncio
import threading

from PySide6.QtCore import QThread, Signal

from workflows.graph import WorkflowGraph
from workflows.runtime import GraphRunResult, GraphRuntime


class NeuralMapWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    node_event = Signal(str, str, object)

    def __init__(
        self,
        runtime: GraphRuntime,
        graph: WorkflowGraph,
        input_text: str,
        *,
        dry_run: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.graph = graph
        self.input_text = input_text
        self.dry_run = dry_run
        self._cancel_requested = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[GraphRunResult] | None = None

    def cancel(self) -> None:
        """Cancel in-flight backend awaits as well as cooperative node boundaries."""
        self._cancel_requested.set()
        loop = self._loop
        task = self._task
        if loop is not None and task is not None and not task.done():
            loop.call_soon_threadsafe(task.cancel)

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        task = loop.create_task(self._execute())
        self._task = task
        try:
            result = loop.run_until_complete(task)
            self.completed.emit(result)
        except asyncio.CancelledError:
            self.completed.emit(
                GraphRunResult(
                    trace_id="",
                    success=False,
                    output=None,
                    trace=[],
                    error={
                        "reason_code": "EXECUTION_CANCELLED",
                        "message": "A execução do NeuralMap foi cancelada.",
                        "alternatives": "Execute novamente quando desejar.",
                    },
                )
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            pending = asyncio.all_tasks(loop)
            for pending_task in pending:
                pending_task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()
            self._task = None
            self._loop = None
            asyncio.set_event_loop(None)

    async def _execute(self) -> GraphRunResult:
        cancel_event = asyncio.Event()

        def on_event(stage: str, status: str, details: dict) -> None:
            self.node_event.emit(stage, status, details)

        runtime = GraphRuntime(self.runtime.handlers, on_event=on_event)
        if self._cancel_requested.is_set():
            cancel_event.set()
        return await runtime.run(
            self.graph,
            self.input_text,
            dry_run=self.dry_run,
            cancel_event=cancel_event,
        )
