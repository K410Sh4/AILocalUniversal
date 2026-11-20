import pytest

from knowledge.evaluation import evaluate_rankings


def test_evaluation_metrics_calculate_precision_recall_mrr_and_coverage() -> None:
    result = evaluate_rankings(
        [["doc-a", "doc-b"], ["doc-c"], ["doc-x"]],
        [{"doc-b"}, {"doc-c"}, {"doc-y"}],
        k=2,
    )

    assert result["queries"] == 3
    assert result["precision_at_k"] == pytest.approx(1 / 3)
    assert result["recall_at_k"] == pytest.approx(2 / 3)
    assert result["mrr"] == pytest.approx(0.5)
    assert result["coverage"] == pytest.approx(2 / 3)


def test_evaluation_deduplicates_multiple_chunks_from_same_document() -> None:
    result = evaluate_rankings(
        [["doc-a", "doc-a", "doc-b"]],
        [{"doc-b"}],
        k=2,
    )

    assert result["precision_at_k"] == pytest.approx(0.5)
    assert result["recall_at_k"] == pytest.approx(1.0)
    assert result["mrr"] == pytest.approx(0.5)
    assert result["coverage"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("rankings", "relevant", "k", "message"),
    [
        ([], [], 1, "pelo menos um"),
        ([["doc-a"]], [set()], 1, "ao menos um documento"),
        ([["doc-a"]], [{"doc-a"}, {"doc-b"}], 1, "Cada ranking"),
        ([["doc-a"]], [{"doc-a"}], 0, "k deve ser positivo"),
    ],
)
def test_evaluation_rejects_invalid_inputs(
    rankings: list[list[str]],
    relevant: list[set[str]],
    k: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        evaluate_rankings(rankings, relevant, k=k)
