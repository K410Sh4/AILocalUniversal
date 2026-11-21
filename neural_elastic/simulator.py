"""Deterministic byte-capacity simulator for MoE expert-weight caches.

This module simulates replacement decisions only. It does not execute model
kernels, predict router outputs, prefetch from storage, or emulate disk latency.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from neural_elastic.contracts import AccessTrace


class CachePolicy(StrEnum):
    """Replacement policies available in the version-1 simulator."""

    LRU = "lru"
    LFU = "lfu"
    STATISTICAL = "statistical"
    BELADY_MIN = "belady_min"


@dataclass(slots=True)
class _CacheEntry:
    size_bytes: int
    last_access: int
    frequency: int


@dataclass(frozen=True, slots=True)
class SimulationMetrics:
    """Cold-start metrics produced by one complete trace simulation."""

    policy: str
    capacity_bytes: int
    total_accesses: int
    unique_tokens: int
    unique_experts: int
    cache_hits: int
    cache_misses: int
    bytes_read: int
    evictions: int
    bypassed_accesses: int
    peak_resident_bytes: int
    peak_resident_experts: int
    final_resident_bytes: int

    @property
    def hit_rate(self) -> float:
        return self.cache_hits / self.total_accesses if self.total_accesses else 0.0

    @property
    def miss_rate(self) -> float:
        return self.cache_misses / self.total_accesses if self.total_accesses else 0.0

    @property
    def bytes_read_per_token(self) -> float:
        return self.bytes_read / self.unique_tokens if self.unique_tokens else 0.0

    def to_dict(self) -> dict[str, int | float | str]:
        """Return a JSON-serializable representation including derived rates."""
        return {
            "policy": self.policy,
            "capacity_bytes": self.capacity_bytes,
            "total_accesses": self.total_accesses,
            "unique_tokens": self.unique_tokens,
            "unique_experts": self.unique_experts,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "bytes_read": self.bytes_read,
            "bytes_read_per_token": self.bytes_read_per_token,
            "evictions": self.evictions,
            "bypassed_accesses": self.bypassed_accesses,
            "peak_resident_bytes": self.peak_resident_bytes,
            "peak_resident_experts": self.peak_resident_experts,
            "final_resident_bytes": self.final_resident_bytes,
        }


def _validate_capacity(capacity_bytes: int) -> None:
    if (
        isinstance(capacity_bytes, bool)
        or not isinstance(capacity_bytes, int)
        or capacity_bytes <= 0
    ):
        raise ValueError("capacity_bytes precisa ser um inteiro positivo.")


def _normalize_policy(policy: CachePolicy | str) -> CachePolicy:
    try:
        return policy if isinstance(policy, CachePolicy) else CachePolicy(policy)
    except (TypeError, ValueError) as exc:
        options = ", ".join(item.value for item in CachePolicy)
        raise ValueError(f"Política inválida; opções: {options}.") from exc


def _statistical_score(
    expert_id: str,
    current_index: int,
    scores: dict[str, tuple[float, int]],
    half_life_accesses: float,
) -> float:
    score, last_update = scores.get(expert_id, (0.0, current_index))
    age = current_index - last_update
    decayed_frequency = score * (0.5 ** (age / half_life_accesses))
    recency_bonus = 1.0 / (1.0 + age)
    return decayed_frequency + recency_bonus


def simulate_trace(
    trace: AccessTrace,
    capacity_bytes: int,
    policy: CachePolicy | str,
    *,
    statistical_half_life: float = 128.0,
) -> SimulationMetrics:
    """Simulate a cold cache against an ordered sequence of expert accesses.

    LRU and LFU support variable expert sizes. The statistical policy combines
    exponentially decayed reuse frequency with a recency bonus. Belady MIN is
    an offline oracle and is intentionally restricted to equal-sized experts:
    farthest-next-use is not generally optimal for variable-sized objects.
    """
    if not isinstance(trace, AccessTrace):
        raise TypeError("trace precisa ser uma instância de AccessTrace.")
    _validate_capacity(capacity_bytes)
    selected_policy = _normalize_policy(policy)

    if selected_policy is CachePolicy.STATISTICAL:
        if (
            isinstance(statistical_half_life, bool)
            or not isinstance(statistical_half_life, (int, float))
            or not isfinite(statistical_half_life)
            or statistical_half_life <= 0
        ):
            raise ValueError("statistical_half_life precisa ser um número positivo.")
    if (
        selected_policy is CachePolicy.BELADY_MIN
        and not trace.has_uniform_expert_sizes
    ):
        raise ValueError(
            "Belady MIN só é reportado como limite teórico para especialistas "
            "de tamanho uniforme."
        )

    positions_by_expert: dict[str, list[int]] = {}
    if selected_policy is CachePolicy.BELADY_MIN:
        for index, event in enumerate(trace.events):
            positions_by_expert.setdefault(event.expert_id, []).append(index)

    cache: dict[str, _CacheEntry] = {}
    resident_bytes = 0
    peak_resident_bytes = 0
    peak_resident_experts = 0
    cache_hits = 0
    cache_misses = 0
    bytes_read = 0
    evictions = 0
    bypassed_accesses = 0
    statistical_scores: dict[str, tuple[float, int]] = {}

    for index, event in enumerate(trace.events):
        expert_id = event.expert_id

        if selected_policy is CachePolicy.STATISTICAL:
            previous_score, previous_index = statistical_scores.get(
                expert_id, (0.0, index)
            )
            elapsed = index - previous_index
            decayed = previous_score * (
                0.5 ** (elapsed / statistical_half_life)
            )
            statistical_scores[expert_id] = (decayed + 1.0, index)

        cached = cache.get(expert_id)
        if cached is not None:
            cache_hits += 1
            cached.last_access = index
            cached.frequency += 1
            continue

        cache_misses += 1
        bytes_read += event.size_bytes
        if event.size_bytes > capacity_bytes:
            bypassed_accesses += 1
            continue

        while resident_bytes + event.size_bytes > capacity_bytes:
            if selected_policy is CachePolicy.LRU:
                victim = min(
                    cache,
                    key=lambda key: (cache[key].last_access, key),
                )
            elif selected_policy is CachePolicy.LFU:
                victim = min(
                    cache,
                    key=lambda key: (
                        cache[key].frequency,
                        cache[key].last_access,
                        key,
                    ),
                )
            elif selected_policy is CachePolicy.STATISTICAL:
                victim = min(
                    cache,
                    key=lambda key: (
                        _statistical_score(
                            key,
                            index,
                            statistical_scores,
                            statistical_half_life,
                        ),
                        cache[key].last_access,
                        key,
                    ),
                )
            else:
                def next_use(key: str) -> float | int:
                    positions = positions_by_expert.get(key, [])
                    next_index = bisect_right(positions, index)
                    return (
                        positions[next_index]
                        if next_index < len(positions)
                        else float("inf")
                    )

                victim = max(
                    cache,
                    key=lambda key: (
                        next_use(key),
                        -cache[key].last_access,
                        key,
                    ),
                )

            removed = cache.pop(victim)
            resident_bytes -= removed.size_bytes
            evictions += 1

        cache[expert_id] = _CacheEntry(
            size_bytes=event.size_bytes,
            last_access=index,
            frequency=1,
        )
        resident_bytes += event.size_bytes
        peak_resident_bytes = max(peak_resident_bytes, resident_bytes)
        peak_resident_experts = max(peak_resident_experts, len(cache))

    return SimulationMetrics(
        policy=selected_policy.value,
        capacity_bytes=capacity_bytes,
        total_accesses=len(trace.events),
        unique_tokens=trace.token_count,
        unique_experts=len(trace.expert_sizes),
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        bytes_read=bytes_read,
        evictions=evictions,
        bypassed_accesses=bypassed_accesses,
        peak_resident_bytes=peak_resident_bytes,
        peak_resident_experts=peak_resident_experts,
        final_resident_bytes=resident_bytes,
    )


def compare_policies(
    trace: AccessTrace,
    capacity_bytes: int,
    *,
    include_belady: bool = True,
    statistical_half_life: float = 128.0,
) -> tuple[SimulationMetrics, ...]:
    """Compare online baselines and, when valid, the Belady MIN oracle."""
    policies: list[CachePolicy] = [
        CachePolicy.LRU,
        CachePolicy.LFU,
        CachePolicy.STATISTICAL,
    ]
    if include_belady and trace.has_uniform_expert_sizes:
        policies.append(CachePolicy.BELADY_MIN)
    return tuple(
        simulate_trace(
            trace,
            capacity_bytes,
            policy,
            statistical_half_life=statistical_half_life,
        )
        for policy in policies
    )
