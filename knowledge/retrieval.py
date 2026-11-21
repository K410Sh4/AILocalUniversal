"""Recuperação lexical e contrato de fusão híbrida por Reciprocal Rank Fusion."""

from __future__ import annotations

from dataclasses import replace

from knowledge.errors import KnowledgeIndexError
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.models import Reranker, SearchHit, VectorSearchBackend


class HybridRetriever:
    """Combina rankings lexical e vetorial quando um backend vetorial é fornecido."""

    def __init__(
        self,
        lexical_index: SQLiteKnowledgeIndex,
        vector_backend: VectorSearchBackend | None = None,
        reranker: Reranker | None = None,
        rrf_constant: int = 60,
    ) -> None:
        if rrf_constant < 1:
            raise ValueError("rrf_constant deve ser positivo.")
        self.lexical_index = lexical_index
        self.vector_backend = vector_backend
        self.reranker = reranker
        self.rrf_constant = rrf_constant

    def search(
        self,
        query: str,
        limit: int = 8,
        document_ids: set[str] | None = None,
    ) -> list[SearchHit]:
        if limit < 1:
            raise ValueError("limit deve ser positivo.")
        candidate_limit = max(limit * 3, limit)
        lexical = self.lexical_index.search(
            query,
            limit=candidate_limit,
            document_ids=document_ids,
        )
        rankings: list[tuple[str, list[SearchHit]]] = [("lexical", lexical)]

        if self.vector_backend is not None:
            vector = self.vector_backend.search(
                query,
                limit=candidate_limit,
                document_ids=document_ids,
            )
            if document_ids is not None:
                vector = [
                    hit for hit in vector if hit.chunk.document_id in document_ids
                ]
            rankings.append(("vector", vector))

        fused: dict[str, dict[str, object]] = {}
        for source_name, hits in rankings:
            seen_in_source: set[str] = set()
            for rank, hit in enumerate(hits, start=1):
                chunk_id = hit.chunk.chunk_id
                if chunk_id in seen_in_source:
                    continue
                seen_in_source.add(chunk_id)
                entry = fused.setdefault(
                    chunk_id,
                    {
                        "chunk": hit.chunk,
                        "score": 0.0,
                        "sources": set(),
                    },
                )
                entry["score"] = float(entry["score"]) + (
                    1.0 / (self.rrf_constant + rank)
                )
                sources = entry["sources"]
                if isinstance(sources, set):
                    sources.add(source_name)

        ordered = sorted(
            fused.values(),
            key=lambda item: (
                -float(item["score"]),
                str(getattr(item["chunk"], "chunk_id", "")),
            ),
        )
        results = [
            SearchHit(
                chunk=item["chunk"],
                score=float(item["score"]),
                rank=rank,
                retrieval_sources=tuple(sorted(item["sources"])),
            )
            for rank, item in enumerate(ordered[:candidate_limit], start=1)
        ]

        if self.reranker is not None and results:
            reranked = self.reranker.rerank(query, results)
            allowed = {hit.chunk.chunk_id for hit in results}
            received: set[str] = set()
            for hit in reranked:
                chunk_id = hit.chunk.chunk_id
                if chunk_id not in allowed or chunk_id in received:
                    raise KnowledgeIndexError(
                        "O reranker tentou adicionar ou duplicar uma evidência candidata."
                    )
                received.add(chunk_id)
            results = [
                replace(hit, rank=rank)
                for rank, hit in enumerate(reranked, start=1)
            ]

        return results[:limit]
