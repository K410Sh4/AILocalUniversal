"""Classificador multilabel NAPA, baseado em sinais heurísticos explicáveis."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from math import isfinite

from core.capability_vectorizer import CAPABILITY_DIMENSIONS, CapabilityVectorizer
from napa.contracts import AreaActivation, NapaClassification
from napa.registry import CognitiveAreaRegistry, create_default_registry


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


class CognitiveAreaClassifier:
    """Ativa várias áreas sem tratá-las como probabilidades nem escolher modelos."""

    VERSION = "napa-1.0"
    _INTENT_AFFINITY = 0.78
    _ANCHOR_AFFINITY = 0.27

    def __init__(
        self,
        registry: CognitiveAreaRegistry | None = None,
        vectorizer: CapabilityVectorizer | None = None,
    ) -> None:
        self.registry = registry if registry is not None else create_default_registry()
        self.vectorizer = vectorizer or CapabilityVectorizer()

    @staticmethod
    def _validate_capability_scores(
        capability_scores: Mapping[str, float],
    ) -> dict[str, float]:
        unknown = set(capability_scores) - set(CAPABILITY_DIMENSIONS)
        if unknown:
            raise ValueError(
                f"Dimensões de capacidade desconhecidas: {', '.join(sorted(unknown))}"
            )

        validated: dict[str, float] = {}
        for name, score in capability_scores.items():
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not isfinite(score)
                or not 0.0 <= score <= 1.0
            ):
                raise ValueError(f"Score inválido para {name}: esperado valor entre 0 e 1.")
            validated[name] = float(score)
        return validated

    @staticmethod
    def _matches_anchor(text: str, anchor: str) -> bool:
        folded_anchor = _fold(anchor.strip())
        if not folded_anchor:
            return False
        pattern = rf"(?<!\w){re.escape(folded_anchor)}(?!\w)"
        return re.search(pattern, text) is not None

    def classify(
        self,
        text: str,
        *,
        intent: str | None = None,
        capability_scores: Mapping[str, float] | None = None,
    ) -> NapaClassification:
        if not isinstance(text, str):
            raise TypeError("text precisa ser string.")

        normalized = _fold(text)
        scores = (
            self._validate_capability_scores(capability_scores)
            if capability_scores is not None
            else self.vectorizer.classify(text).to_dict()
        )

        activations: list[AreaActivation] = []
        for area in self.registry.areas:
            signals: list[str] = []
            affinity = 0.0

            for dimension in area.capability_dimensions:
                value = scores.get(dimension, 0.0)
                if value > 0:
                    affinity = max(affinity, value)
                    signals.append(f"capability:{dimension}")

            if intent and intent in area.intents:
                affinity = max(affinity, self._INTENT_AFFINITY)
                signals.append(f"intent:{intent}")

            matched_anchors = [
                anchor for anchor in area.anchors
                if self._matches_anchor(normalized, anchor)
            ]
            if matched_anchors:
                anchor_affinity = min(
                    0.96, len(matched_anchors) * self._ANCHOR_AFFINITY
                )
                affinity = max(affinity, anchor_affinity)
                signals.extend(f"anchor:{anchor}" for anchor in matched_anchors)

            if affinity >= area.minimum_affinity:
                activations.append(
                    AreaActivation(
                        area_id=area.area_id,
                        kind=area.kind,
                        affinity=round(affinity, 3),
                        signals=tuple(signals),
                    )
                )

        activations.sort(key=lambda item: (-item.affinity, item.area_id))
        return NapaClassification(
            activations=tuple(activations),
            classifier_version=self.VERSION,
        )
