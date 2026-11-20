"""Normalização segura e preservação da entrada original."""

from __future__ import annotations

import unicodedata

from core.cognitive_task import CognitiveTask


MAX_INPUT_CHARACTERS = 32_000


class InputValidationError(ValueError):
    """A entrada excede os limites ou não contém texto utilizável."""


def normalize_input(text: str) -> str:
    """Normaliza Unicode e espaços horizontais sem remover quebras de parágrafo."""
    if not isinstance(text, str):
        raise InputValidationError("A entrada precisa ser texto.")
    if len(text) > MAX_INPUT_CHARACTERS:
        raise InputValidationError(
            f"A entrada excede o limite de {MAX_INPUT_CHARACTERS} caracteres."
        )

    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    safe_characters = (
        character
        for character in normalized
        if character in {"\n", "\t"} or unicodedata.category(character) != "Cc"
    )
    lines = [" ".join(line.split()) for line in "".join(safe_characters).split("\n")]
    result = "\n".join(lines).strip()
    if not result:
        raise InputValidationError("Digite uma mensagem antes de enviar.")
    return result


class InputProcessingStage:
    """Primeira etapa do pipeline cognitivo."""

    name = "input_processing"

    async def process(self, task: CognitiveTask) -> CognitiveTask:
        task.normalized_text = normalize_input(task.original_text)
        return task
