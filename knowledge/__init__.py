"""Ingestão, indexação e recuperação de conhecimento local."""

from knowledge.chunking import DocumentChunker
from knowledge.context import ContextComposer
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.ingestion import DocumentIngestor
from knowledge.runtime import KnowledgeRuntime
from knowledge.loaders import LoaderRegistry, MarkdownLoader, PdfLoader, TextLoader
from knowledge.retrieval import HybridRetriever
from knowledge.validation import EvidenceValidator
from knowledge.vectors import (
    LocalVectorIndexer,
    OllamaEmbeddingProvider,
    SQLiteVectorSearchBackend,
    SQLiteVectorStore,
)

__all__ = [
    "DocumentChunker",
    "ContextComposer",
    "DocumentIngestor",
    "EvidenceValidator",
    "HybridRetriever",
    "KnowledgeRuntime",
    "LoaderRegistry",
    "LocalVectorIndexer",
    "MarkdownLoader",
    "OllamaEmbeddingProvider",
    "PdfLoader",
    "SQLiteKnowledgeIndex",
    "SQLiteVectorSearchBackend",
    "SQLiteVectorStore",
    "TextLoader",
]
