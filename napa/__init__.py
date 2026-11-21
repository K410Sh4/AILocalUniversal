"""Neural Adaptive Plasticity Architecture."""

from napa.classifier import CognitiveAreaClassifier
from napa.contracts import (
    AreaActivation,
    CognitiveArea,
    CognitiveAreaKind,
    NapaClassification,
)
from napa.registry import (
    DEFAULT_COGNITIVE_AREAS,
    CognitiveAreaRegistry,
    create_default_registry,
)

__all__ = [
    "AreaActivation",
    "CognitiveArea",
    "CognitiveAreaClassifier",
    "CognitiveAreaKind",
    "CognitiveAreaRegistry",
    "DEFAULT_COGNITIVE_AREAS",
    "NapaClassification",
    "create_default_registry",
]
