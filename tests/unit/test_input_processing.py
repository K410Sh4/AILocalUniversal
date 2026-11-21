import pytest

from core.cognitive_task import CognitiveTask
from core.input_processing import InputProcessingStage, InputValidationError, normalize_input


def test_normalization_preserves_paragraphs_and_normalizes_spaces() -> None:
    assert normalize_input("  Olá   mundo  \r\n\r\n  segunda   linha  ") == (
        "Olá mundo\n\nsegunda linha"
    )


def test_normalization_rejects_empty_and_oversized_input() -> None:
    with pytest.raises(InputValidationError):
        normalize_input(" \n\t ")
    with pytest.raises(InputValidationError):
        normalize_input("x" * 32_001)


@pytest.mark.asyncio
async def test_input_stage_preserves_original_text() -> None:
    task = CognitiveTask(original_text="  Olá   mundo  ")
    await InputProcessingStage().process(task)

    assert task.original_text == "  Olá   mundo  "
    assert task.normalized_text == "Olá mundo"
