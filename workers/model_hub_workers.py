"""Workers Qt do NeuralModel Hub: catálogo, pull e remoção de modelos."""

from __future__ import annotations

import asyncio

from PySide6.QtCore import QThread, Signal

from engines.ollama_engine import OllamaEngine
from model_hub.catalog import CatalogDocument, ModelCatalogClient
from workers.ollama_workers import _AsyncWorker


class ModelCatalogWorker(QThread):
    """Atualiza o catálogo de modelos fora da thread da interface."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, client: ModelCatalogClient | None = None, parent=None) -> None:
        super().__init__(parent)
        self.client = client or ModelCatalogClient()

    def run(self) -> None:
        try:
            document: CatalogDocument = asyncio.run(self.client.fetch())
            self.completed.emit(document)
        except Exception as exc:
            self.failed.emit(str(exc))


class OllamaPullWorker(_AsyncWorker):
    """Executa pull cancelável e transmite os eventos de progresso do Ollama."""

    progress = Signal(object)

    def __init__(self, engine: OllamaEngine, model_reference: str, parent=None) -> None:
        super().__init__(engine, parent)
        self.model_reference = model_reference

    async def execute(self) -> None:
        async for event in self.engine.pull_model(self.model_reference):
            self.progress.emit(event)
        self.completed.emit(
            {"model": self.model_reference, "status": "success"}
        )


class OllamaDeleteWorker(_AsyncWorker):
    """Remove um modelo local depois de confirmação explícita na interface."""

    def __init__(self, engine: OllamaEngine, model_reference: str, parent=None) -> None:
        super().__init__(engine, parent)
        self.model_reference = model_reference

    async def execute(self) -> None:
        await self.engine.delete_model(self.model_reference)
        self.completed.emit(
            {"model": self.model_reference, "status": "deleted"}
        )
