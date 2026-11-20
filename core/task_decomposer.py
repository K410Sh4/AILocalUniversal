"""Decomposição heurística de pedidos compostos em subtarefas estruturadas.

Só decompõe quando a estrutura é explícita (listas ou conectores sequenciais).
Não executa subtarefas nem cria agentes; produz um plano para orientar a síntese.
"""

from __future__ import annotations

import re

from core.capability_vectorizer import CapabilityVectorizer
from core.cognitive_task import CognitiveTask
from core.semantic_analysis import classify_intent


_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$")
_SEQUENCE_SPLITTER = re.compile(
    r"\s+(?:e\s+depois|depois disso|em seguida|na sequência|por fim|depois|then|next)\s+",
    re.IGNORECASE,
)
_MAX_SUBTASKS = 6


def _visible_lines(text: str) -> list[str]:
    """Remove linhas dentro de blocos de código para evitar decomposição acidental."""
    visible: list[str] = []
    fence: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = "```" if stripped.startswith("```") else "~~~"
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            visible.append(line)
    return visible


def _from_explicit_list(lines: list[str]) -> list[str] | None:
    bullet_indices: list[int] = []
    bullet_texts: list[str] = []

    for index, line in enumerate(lines):
        match = _BULLET.match(line)
        if match:
            bullet_indices.append(index)
            bullet_texts.append(match.group(1).strip())

    if not 2 <= len(bullet_texts) <= _MAX_SUBTASKS:
        return None

    context = " ".join(
        part.strip()
        for part in lines[: bullet_indices[0]]
        if part.strip()
    )
    if context:
        return [f"{context} {item}" for item in bullet_texts]
    return bullet_texts


def _split_sequence(text: str) -> tuple[list[str], str] | None:
    parts = [part.strip(" ,;:.") for part in _SEQUENCE_SPLITTER.split(text)]
    parts = [part for part in parts if part]
    if 2 <= len(parts) <= _MAX_SUBTASKS:
        return parts, "sequential"
    return None


def _split_semicolon_clauses(text: str) -> tuple[list[str], str] | None:
    parts = [part.strip(" ,;:.") for part in text.split(";")]
    parts = [part for part in parts if part]
    if 2 <= len(parts) <= _MAX_SUBTASKS:
        return parts, "independent"
    return None


class TaskDecomposer:
    """Produz um DAG pequeno a partir de estrutura explícita no pedido."""

    def __init__(
        self,
        vectorizer: CapabilityVectorizer | None = None,
        max_subtasks: int = _MAX_SUBTASKS,
    ) -> None:
        if not 2 <= max_subtasks <= _MAX_SUBTASKS:
            raise ValueError(f"max_subtasks deve estar entre 2 e {_MAX_SUBTASKS}.")
        self.vectorizer = vectorizer or CapabilityVectorizer()
        self.max_subtasks = max_subtasks

    def decompose(self, task: CognitiveTask) -> CognitiveTask:
        text = task.normalized_text or task.original_text
        lines = _visible_lines(text)
        list_parts = _from_explicit_list(lines)

        if list_parts is not None and len(list_parts) <= self.max_subtasks:
            parts = list_parts
            strategy = "independent"
        else:
            visible_text = " ".join(line.strip() for line in lines if line.strip())
            sequence = _split_sequence(visible_text)
            if sequence is not None and len(sequence[0]) <= self.max_subtasks:
                parts, strategy = sequence
            else:
                semicolon_parts = _split_semicolon_clauses(visible_text)
                if semicolon_parts is None or len(semicolon_parts[0]) > self.max_subtasks:
                    task.subtasks = []
                    task.subtask_plan = []
                    return task
                parts, strategy = semicolon_parts

        if len(parts) < 2:
            task.subtasks = []
            task.subtask_plan = []
            return task

        plan: list[dict[str, object]] = []
        for order, part in enumerate(parts, start=1):
            subtask_id = f"{task.task_id}:subtask:{order:02d}"
            dependencies = (
                [f"{task.task_id}:subtask:{order - 1:02d}"]
                if strategy == "sequential" and order > 1
                else []
            )
            plan.append(
                {
                    "id": subtask_id,
                    "order": order,
                    "text": part,
                    "intent": classify_intent(part),
                    "capabilities": self.vectorizer.classify(part).to_dict(),
                    "depends_on": dependencies,
                    "strategy": strategy,
                    "status": "pending",
                }
            )

        task.subtasks = [str(item["id"]) for item in plan]
        task.subtask_plan = plan
        return task


class TaskDecompositionStage:
    """Etapa do Task Decomposer no pipeline assíncrono."""

    name = "task_decomposition"

    def __init__(self, decomposer: TaskDecomposer | None = None) -> None:
        self.decomposer = decomposer or TaskDecomposer()

    async def process(self, task: CognitiveTask) -> CognitiveTask:
        return self.decomposer.decompose(task)
