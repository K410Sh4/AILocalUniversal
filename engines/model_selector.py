"""Seleção determinística de modelo para o modo automático inicial."""

from __future__ import annotations

from engines.base import ModelInfo


class ModelSelectionError(RuntimeError):
    """Não existe modelo elegível para a tarefa."""


def choose_model(models: list[ModelInfo], preferred_model: str | None = None) -> ModelInfo:
    """Escolhe o preferido disponível ou o primeiro nome em ordem estável.

    O roteamento semântico por capacidade e dificuldade será implementado na Fase 2.
    """
    candidates = [
        model for model in models if model.capabilities.verified and model.capabilities.chat
    ]
    if not candidates:
        raise ModelSelectionError(
            "Nenhum modelo de chat está disponível. Instale um modelo no Ollama."
        )
    if preferred_model:
        for model in candidates:
            if model.name == preferred_model:
                return model
    return sorted(candidates, key=lambda model: model.name.casefold())[0]
