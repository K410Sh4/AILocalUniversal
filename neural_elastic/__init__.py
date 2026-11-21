"""Neural Elastic Execution: deterministic expert-cache research tools."""

from neural_elastic.contracts import AccessTrace, ExpertAccess, TraceFormatError
from neural_elastic.simulator import (
    CachePolicy,
    SimulationMetrics,
    compare_policies,
    simulate_trace,
)
from neural_elastic.synthetic import generate_synthetic_trace

__all__ = [
    "AccessTrace",
    "CachePolicy",
    "ExpertAccess",
    "SimulationMetrics",
    "TraceFormatError",
    "compare_policies",
    "generate_synthetic_trace",
    "simulate_trace",
]
