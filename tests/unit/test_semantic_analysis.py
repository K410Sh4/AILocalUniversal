import pytest

from core.cognitive_task import CognitiveTask
from core.input_processing import InputProcessingStage
from core.semantic_analysis import SemanticAnalysisStage, classify_intent


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Calcule 12 * 4", "calculation"),
        ("Converta 5 km para m", "unit_conversion"),
        ("Explique como funciona uma integral", "explanation"),
        ("Escreva um e-mail formal", "writing"),
        ("Compare duas arquiteturas", "comparison"),
        ("Revise este código Python", "programming"),
    ],
)
def test_intent_classification(text: str, expected: str) -> None:
    assert classify_intent(text) == expected


@pytest.mark.asyncio
async def test_semantic_stage_sets_separate_indicators() -> None:
    task = CognitiveTask(original_text="Urgente: explique a dose deste medicamento.")
    await InputProcessingStage().process(task)
    await SemanticAnalysisStage().process(task)

    assert task.intent == "explanation"
    assert task.risk is not None and task.risk > 0.5
    assert task.urgency is not None and task.urgency > 0.5
    assert task.difficulty is not None
    assert task.uncertainty is not None
    assert len(task.capabilities) == 12
