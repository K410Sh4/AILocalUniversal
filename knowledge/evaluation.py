"""Métricas reproduzíveis para avaliar rankings de recuperação documental."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def _unique_in_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def evaluate_rankings(
    rankings: Sequence[Sequence[str]],
    relevant_document_ids: Sequence[set[str] | frozenset[str]],
    *,
    k: int = 5,
) -> dict[str, Any]:
    """Calcula precision@k, recall@k, MRR e cobertura em nível de documento.

    Rankings devem conter document IDs em ordem decrescente de relevância estimada.
    IDs repetidos (por exemplo, múltiplos chunks do mesmo arquivo) contam uma vez.
    Precision@k usa k como denominador mesmo quando há menos de k resultados.
    """
    if k < 1:
        raise ValueError("k deve ser positivo.")
    if len(rankings) != len(relevant_document_ids):
        raise ValueError("Cada ranking precisa ter seu conjunto de documentos relevantes.")
    if not rankings:
        raise ValueError("É necessário pelo menos um caso de avaliação.")
    if any(not relevant for relevant in relevant_document_ids):
        raise ValueError("Cada caso precisa ter ao menos um documento relevante.")

    per_query: list[dict[str, float | int]] = []
    for ranking, relevant in zip(rankings, relevant_document_ids, strict=True):
        unique_ranking = _unique_in_order(ranking)
        top_k = unique_ranking[:k]
        hits = [document_id for document_id in top_k if document_id in relevant]
        first_rank = next(
            (
                rank
                for rank, document_id in enumerate(unique_ranking, start=1)
                if document_id in relevant
            ),
            None,
        )
        precision = len(hits) / k
        recall = len(hits) / len(relevant)
        reciprocal_rank = 1.0 / first_rank if first_rank is not None else 0.0
        per_query.append(
            {
                "precision_at_k": precision,
                "recall_at_k": recall,
                "reciprocal_rank": reciprocal_rank,
                "covered": int(bool(hits)),
            }
        )

    count = len(per_query)
    return {
        "queries": count,
        "k": k,
        "precision_at_k": sum(row["precision_at_k"] for row in per_query) / count,
        "recall_at_k": sum(row["recall_at_k"] for row in per_query) / count,
        "mrr": sum(row["reciprocal_rank"] for row in per_query) / count,
        "coverage": sum(row["covered"] for row in per_query) / count,
        "per_query": per_query,
    }
