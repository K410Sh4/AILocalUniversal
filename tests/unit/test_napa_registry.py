from __future__ import annotations

import math

import pytest

from core.capability_vectorizer import CAPABILITY_DIMENSIONS
from core.cognitive_task import CognitiveTask
from core.input_processing import InputProcessingStage
from core.semantic_analysis import SemanticAnalysisStage
from napa import (
    CognitiveArea,
    CognitiveAreaClassifier,
    CognitiveAreaKind,
    CognitiveAreaRegistry,
    create_default_registry,
)


def test_default_registry_has_unique_areas_and_all_three_component_kinds() -> None:
    registry = create_default_registry()

    assert len(registry) >= 10
    assert len(registry.area_ids) == len(set(registry.area_ids))
    assert {area.kind for area in registry.areas} == {
        CognitiveAreaKind.DETERMINISTIC_TOOL,
        CognitiveAreaKind.COGNITIVE_CAPABILITY,
        CognitiveAreaKind.NEURAL_SPECIALIST,
    }


def test_multilabel_classifier_activates_independent_capabilities() -> None:
    text = (
        "Crie uma função Python para calcular juros compostos e explique "
        "de maneira simples e educada."
    )

    result = CognitiveAreaClassifier().classify(text, intent="programming")

    active = set(result.active_area_ids)
    assert {
        "programming",
        "mathematics",
        "generation",
        "communication",
        "social_cordiality",
    } <= active
    assert "conversion" not in active
    assert result.method == "lexical_capability_intent_heuristics"
    assert result.to_dict()["score_semantics"] == "heuristic_affinity_not_probability"
    assert all(0.0 <= item.affinity <= 1.0 for item in result.activations)


def test_deterministic_conversion_is_separated_from_neural_specialists() -> None:
    result = CognitiveAreaClassifier().classify(
        "Converta 5 km para metros.",
        intent="unit_conversion",
    )
    by_id = {item.area_id: item for item in result.activations}

    assert "conversion" in by_id
    assert by_id["conversion"].kind is CognitiveAreaKind.DETERMINISTIC_TOOL
    assert "programming" not in by_id
    assert "perception" not in by_id


def test_pure_calculation_activates_math_and_tool_use_without_forcing_llm() -> None:
    result = CognitiveAreaClassifier().classify(
        "Calcule 15% de 850.",
        intent="calculation",
    )
    by_id = {item.area_id: item for item in result.activations}

    assert "mathematics" in by_id
    assert "tool_use" in by_id
    assert by_id["mathematics"].kind is CognitiveAreaKind.DETERMINISTIC_TOOL
    assert "programming" not in by_id


def test_classifier_uses_provided_vectorizer_scores_without_reclassifying() -> None:
    scores = {dimension: 0.0 for dimension in CAPABILITY_DIMENSIONS}
    scores["vision_multimodal"] = 0.61

    result = CognitiveAreaClassifier().classify(
        "interprete o anexo",
        capability_scores=scores,
    )

    active = {item.area_id for item in result.activations}
    assert "perception" in active


def test_custom_registry_accepts_new_declarative_area() -> None:
    custom = CognitiveArea(
        area_id="bioinformatics",
        name="Bioinformatics",
        kind=CognitiveAreaKind.NEURAL_SPECIALIST,
        description="Análise de sequências biológicas.",
        anchors=("genomica", "sequenciamento"),
    )
    registry = CognitiveAreaRegistry((custom,))

    result = CognitiveAreaClassifier(registry=registry).classify(
        "Explique a genômica."
    )

    assert result.active_area_ids == ("bioinformatics",)


def test_registry_rejects_duplicate_ids_and_unknown_dimensions() -> None:
    area = CognitiveArea(
        area_id="math_custom",
        name="Matemática",
        kind=CognitiveAreaKind.DETERMINISTIC_TOOL,
        description="Teste.",
    )
    registry = CognitiveAreaRegistry((area,))

    with pytest.raises(ValueError, match="já registrada"):
        registry.register(area)

    with pytest.raises(ValueError, match="Dimensões desconhecidas"):
        CognitiveArea(
            area_id="invalid",
            name="Inválida",
            kind=CognitiveAreaKind.COGNITIVE_CAPABILITY,
            description="Teste.",
            capability_dimensions=("not_a_capability",),
        )


@pytest.mark.parametrize("score", [-0.1, 1.1, math.nan, math.inf, True])
def test_classifier_rejects_invalid_capability_scores(score: float) -> None:
    with pytest.raises(ValueError, match="Score inválido"):
        CognitiveAreaClassifier().classify(
            "calcule",
            capability_scores={"math_logic": score},
        )


@pytest.mark.asyncio
async def test_semantic_stage_populates_napa_areas_on_cognitive_task() -> None:
    task = CognitiveTask(
        original_text="Crie uma função Python para calcular juros compostos."
    )
    await InputProcessingStage().process(task)
    await SemanticAnalysisStage().process(task)

    assert task.cognitive_areas["classifier_version"] == "napa-1.0"
    assert "programming" in task.cognitive_areas["active_areas"]
    assert "mathematics" in task.cognitive_areas["active_areas"]


def test_cognitive_task_round_trips_napa_areas_and_reads_legacy_payload() -> None:
    task = CognitiveTask(
        original_text="Crie uma função Python.",
        cognitive_areas={
            "schema_version": "1.0",
            "active_areas": ["programming"],
            "activations": [],
        },
    )
    restored = CognitiveTask.from_dict(task.to_dict())

    assert restored.cognitive_areas == task.cognitive_areas

    legacy_payload = task.to_dict()
    legacy_payload.pop("cognitive_areas")
    assert CognitiveTask.from_dict(legacy_payload).cognitive_areas == {}
