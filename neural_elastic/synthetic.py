"""Reproducible synthetic MoE routing traces for simulator smoke tests."""

from __future__ import annotations

import random

from neural_elastic.contracts import AccessTrace, ExpertAccess


def generate_synthetic_trace(
    token_count: int,
    expert_count: int,
    *,
    top_k: int = 2,
    expert_size_bytes: int = 4 * 1024 * 1024,
    workload: str = "phased",
    phase_tokens: int = 500,
    hot_set_size: int | None = None,
    seed: int = 42,
) -> AccessTrace:
    """Generate a deterministic stationary, phased, or uniform access trace.

    This generator is only a controlled workload fixture. Its events are not
    captured from a real model router and must never be described as hardware
    benchmark results.
    """
    integer_values = {
        "token_count": token_count,
        "expert_count": expert_count,
        "top_k": top_k,
        "expert_size_bytes": expert_size_bytes,
        "phase_tokens": phase_tokens,
        "seed": seed,
    }
    for name, value in integer_values.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} precisa ser inteiro.")
    if token_count < 0:
        raise ValueError("token_count não pode ser negativo.")
    if expert_count <= 0:
        raise ValueError("expert_count precisa ser positivo.")
    if top_k <= 0 or top_k > expert_count:
        raise ValueError("top_k precisa estar entre 1 e expert_count.")
    if expert_size_bytes <= 0:
        raise ValueError("expert_size_bytes precisa ser positivo.")
    if phase_tokens <= 0:
        raise ValueError("phase_tokens precisa ser positivo.")
    if workload not in {"stationary", "phased", "uniform"}:
        raise ValueError("workload deve ser stationary, phased ou uniform.")

    selected_hot_size = hot_set_size or min(expert_count, max(top_k, 8))
    if (
        isinstance(selected_hot_size, bool)
        or not isinstance(selected_hot_size, int)
        or selected_hot_size < top_k
        or selected_hot_size > expert_count
    ):
        raise ValueError("hot_set_size precisa estar entre top_k e expert_count.")

    rng = random.Random(seed)
    events: list[ExpertAccess] = []
    all_experts = list(range(expert_count))

    for token_index in range(token_count):
        if workload == "phased":
            phase = token_index // phase_tokens
            start = (phase * selected_hot_size) % expert_count
            hot_experts = [
                (start + offset) % expert_count
                for offset in range(selected_hot_size)
            ]
            candidate_pool = (
                all_experts if rng.random() < 0.1 else hot_experts
            )
        else:
            candidate_pool = all_experts

        if workload == "uniform":
            weights = [1.0] * len(candidate_pool)
        else:
            weights = [
                1.0 / ((rank + 1) ** 1.15)
                for rank in range(len(candidate_pool))
            ]

        selected: set[int] = set()
        while len(selected) < top_k:
            chosen = rng.choices(candidate_pool, weights=weights, k=1)[0]
            selected.add(chosen)

        for expert_index in sorted(selected):
            events.append(
                ExpertAccess(
                    token_index=token_index,
                    expert_id=f"layer.0/expert.{expert_index}",
                    size_bytes=expert_size_bytes,
                )
            )

    return AccessTrace(tuple(events))
