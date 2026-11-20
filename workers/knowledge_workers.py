"""Worker Qt para operações documentais fora da thread da interface."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from knowledge.library import KnowledgeLibrary, default_knowledge_directory


class KnowledgeLibraryWorker(QThread):
    """Executa uma operação limitada da biblioteca e devolve apenas dados serializáveis."""

    progress = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        operation: str,
        *,
        data_directory: str | Path | None = None,
        ollama_url: str = "http://127.0.0.1:11434",
        embedding_model: str | None = None,
        file_paths: Sequence[str] = (),
        document_ids: Sequence[str] = (),
        query: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        if operation not in {"list", "ingest", "delete", "search", "reindex"}:
            raise ValueError(f"Operação documental desconhecida: {operation}")
        self.operation = operation
        self.data_directory = (
            Path(data_directory) if data_directory is not None else default_knowledge_directory()
        )
        self.ollama_url = ollama_url
        self.embedding_model = embedding_model
        self.file_paths = tuple(file_paths)
        self.document_ids = tuple(document_ids)
        self.query = query

    def run(self) -> None:
        try:
            with KnowledgeLibrary(
                self.data_directory,
                ollama_url=self.ollama_url,
                embedding_model=self.embedding_model,
            ) as library:
                if self.operation == "list":
                    payload: dict[str, Any] = {
                        "operation": "list",
                        "documents": library.list_documents(),
                    }
                elif self.operation == "ingest":
                    self.progress.emit("Lendo, dividindo e indexando os arquivos selecionados…")
                    result = library.ingest_files(self.file_paths)
                    payload = {
                        "operation": "ingest",
                        "result": result,
                        "documents": library.list_documents(),
                    }
                elif self.operation == "reindex":
                    self.progress.emit("Gerando embeddings para os documentos já indexados…")
                    result = library.reindex_vectors()
                    payload = {
                        "operation": "reindex",
                        "result": result,
                        "documents": library.list_documents(),
                    }
                elif self.operation == "delete":
                    result = library.delete_documents(self.document_ids)
                    payload = {
                        "operation": "delete",
                        "result": result,
                        "documents": library.list_documents(),
                    }
                else:
                    self.progress.emit("Pesquisando no índice local…")
                    bundle = library.search(self.query)
                    payload = {
                        "operation": "search",
                        "text": bundle.text,
                        "char_count": bundle.char_count,
                        "citations": [
                            {
                                "citation_id": citation.citation_id,
                                "title": citation.title,
                                "source_uri": citation.source_uri,
                                "locator": citation.locator,
                            }
                            for citation in bundle.citations
                        ],
                        "skipped_count": len(bundle.skipped_chunk_ids),
                        "warning": library.last_search_warning,
                    }
            self.completed.emit(payload)
        except Exception as exc:
            self.failed.emit(str(exc))


 
class KnowledgeRetrievalWorker(QThread):
    """Recupera contexto local fora da thread gráfica antes da geração."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        query: str,
        *,
        ollama_url: str,
        embedding_model: str | None,
        max_chars: int = 6000,
        limit: int = 8,
        data_directory: str | Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.query = query
        self.ollama_url = ollama_url
        self.embedding_model = embedding_model
        self.max_chars = max_chars
        self.limit = limit
        self.data_directory = (
            Path(data_directory) if data_directory is not None
            else default_knowledge_directory()
        )

    def run(self) -> None:
        try:
            with KnowledgeLibrary(
                self.data_directory,
                ollama_url=self.ollama_url,
                embedding_model=self.embedding_model,
            ) as library:
                bundle = library.search(
                    self.query,
                    max_chars=self.max_chars,
                    limit=self.limit,
                )
                from knowledge.runtime import KnowledgeRuntime

                self.completed.emit(
                    {
                        "bundle": bundle,
                        "message": KnowledgeRuntime.as_untrusted_message(bundle),
                        "warning": library.last_search_warning,
                    }
                )
        except Exception as exc:
            self.failed.emit(str(exc))
