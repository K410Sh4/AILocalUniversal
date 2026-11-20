"""Ingestão, indexação e recuperação de conhecimento local."""

from knowledge.chunking import DocumentChunker
from knowledge.context import ContextComposer
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.ingestion import DocumentIngestor
from knowledge.library import KnowledgeLibrary, default_knowledge_directory
from knowledge.loaders import LoaderRegistry, MarkdownLoader, PdfLoader, TextLoader
from knowledge.retrieval import HybridRetriever
from knowledge.runtime import KnowledgeRuntime
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
    "KnowledgeLibrary",
    "KnowledgeRuntime",
    "default_knowledge_directory",
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
