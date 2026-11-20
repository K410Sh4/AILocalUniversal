"""Ingestão, indexação e recuperação de conhecimento local."""

from knowledge.chunking import DocumentChunker
from knowledge.context import ContextComposer
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.ingestion import DocumentIngestor
from knowledge.loaders import LoaderRegistry, MarkdownLoader, PdfLoader, TextLoader
from knowledge.retrieval import HybridRetriever
from knowledge.validation import EvidenceValidator

__all__ = [
    "DocumentChunker",
    "ContextComposer",
    "DocumentIngestor",
    "EvidenceValidator",
    "HybridRetriever",
    "LoaderRegistry",
    "MarkdownLoader",
    "PdfLoader",
    "SQLiteKnowledgeIndex",
    "TextLoader",
]
