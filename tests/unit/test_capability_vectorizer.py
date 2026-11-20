from core.capability_vectorizer import CAPABILITY_DIMENSIONS, CapabilityVectorizer


def test_vectorizer_returns_all_dimensions_with_math_and_programming_anchors() -> None:
    vector = CapabilityVectorizer().classify(
        "Calcule uma integral em Python e explique a equação física."
    )

    assert tuple(vector.to_dict()) == CAPABILITY_DIMENSIONS
    assert vector.scores["math_logic"] > 0
    assert vector.scores["programming"] > 0
    assert vector.scores["science_knowledge"] > 0
    assert all(0.0 <= value <= 1.0 for value in vector.scores.values())


def test_vectorizer_scores_are_heuristic_and_empty_input_is_zeroed() -> None:
    vector = CapabilityVectorizer().classify("xyz sem âncoras conhecidas")

    assert all(value == 0.0 for value in vector.scores.values())


def test_vectorizer_does_not_match_anchor_inside_another_word() -> None:
    vector = CapabilityVectorizer().classify("O sistema digital e capilar continua estável.")

    assert vector.scores["programming"] == 0.0
