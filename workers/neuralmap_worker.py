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

    def cancel(self) -> None:
        """Request cooperative graph cancellation without blocking the UI."""
        self._cancel_requested.set()

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._execute())
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()
            asyncio.set_event_loop(None)

    async def _execute(self) -> GraphRunResult:
        cancel_event = asyncio.Event()

        def on_event(stage: str, status: str, details: dict) -> None:
            self.node_event.emit(stage, status, details)

        runtime = GraphRuntime(self.runtime.handlers, on_event=on_event)
        task = asyncio.create_task(
            runtime.run(
                self.graph,
                self.input_text,
                dry_run=self.dry_run,
                cancel_event=cancel_event,
            )
        )
        while not task.done():
            if self._cancel_requested.is_set():
                cancel_event.set()
            await asyncio.sleep(0.05)
        return await task
