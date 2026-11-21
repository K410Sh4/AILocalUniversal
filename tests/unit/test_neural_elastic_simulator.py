import json

import pytest

from neural_elastic.contracts import AccessTrace, ExpertAccess, TraceFormatError
from neural_elastic.simulator import (
    CachePolicy,
    compare_policies,
    simulate_trace,
)
from neural_elastic.synthetic import generate_synthetic_trace


def trace_of(*expert_ids: str, size_bytes: int = 1) -> AccessTrace:
    return AccessTrace(
        tuple(
            ExpertAccess(
                token_index=index,
                expert_id=expert_id,
                size_bytes=size_bytes,
            )
            for index, expert_id in enumerate(expert_ids)
        )
    )


def test_lru_counts_hits_misses_evictions_and_bytes_read() -> None:
    trace = AccessTrace(
        (
            ExpertAccess(0, "A", 10),
            ExpertAccess(1, "B", 10),
            ExpertAccess(2, "A", 10),
            ExpertAccess(3, "C", 10),
            ExpertAccess(4, "B", 10),
        )
    )

    result = simulate_trace(trace, 20, CachePolicy.LRU)

    assert result.total_accesses == 5
    assert result.unique_tokens == 5
    assert result.unique_experts == 3
    assert result.cache_hits == 1
    assert result.cache_misses == 4
    assert result.hit_rate == pytest.approx(0.2)
    assert result.bytes_read == 40
    assert result.evictions == 2
    assert result.final_resident_bytes == 20
    assert result.bytes_read_per_token == pytest.approx(8.0)


def test_lfu_retains_a_frequently_used_expert_over_a_recent_one() -> None:
    trace = trace_of("A", "A", "A", "B", "C", "A")

    lru = simulate_trace(trace, 2, CachePolicy.LRU)
    lfu = simulate_trace(trace, 2, CachePolicy.LFU)

    assert lru.cache_misses == 4
    assert lfu.cache_misses == 3
    assert lfu.cache_hits == 3


def test_belady_min_is_an_offline_lower_miss_reference() -> None:
    trace = trace_of("A", "B", "C", "A", "B", "A")

    lru = simulate_trace(trace, 2, CachePolicy.LRU)
    belady = simulate_trace(trace, 2, CachePolicy.BELADY_MIN)

    assert belady.cache_misses == 4
    assert belady.cache_hits == 2
    assert belady.cache_misses <= lru.cache_misses


def test_belady_min_rejects_variable_size_experts() -> None:
    trace = AccessTrace(
        (
            ExpertAccess(0, "small", 4),
            ExpertAccess(1, "large", 8),
            ExpertAccess(2, "small", 4),
        )
    )

    with pytest.raises(ValueError, match="tamanho uniforme"):
        simulate_trace(trace, 12, CachePolicy.BELADY_MIN)


def test_comparison_omits_belady_for_variable_size_trace() -> None:
    trace = AccessTrace(
        (
            ExpertAccess(0, "small", 4),
            ExpertAccess(1, "large", 8),
            ExpertAccess(2, "small", 4),
        )
    )

    results = compare_policies(trace, 12)

    assert [result.policy for result in results] == [
        "lru",
        "lfu",
        "statistical",
    ]


def test_comparison_includes_belady_for_uniform_size_trace() -> None:
    results = compare_policies(trace_of("A", "B", "A"), 2)

    assert [result.policy for result in results] == [
        "lru",
        "lfu",
        "statistical",
        "belady_min",
    ]


def test_statistical_policy_is_deterministic_and_validates_half_life() -> None:
    trace = trace_of("A", "B", "A", "C", "A", "B", "A")

    first = simulate_trace(
        trace,
        2,
        CachePolicy.STATISTICAL,
        statistical_half_life=4,
    )
    second = simulate_trace(
        trace,
        2,
        CachePolicy.STATISTICAL,
        statistical_half_life=4,
    )

    assert first == second
    with pytest.raises(ValueError, match="half_life"):
        simulate_trace(
            trace,
            2,
            CachePolicy.STATISTICAL,
            statistical_half_life=0,
        )


def test_expert_larger_than_cache_is_bypassed_without_evicting_residents() -> None:
    trace = AccessTrace(
        (
            ExpertAccess(0, "resident", 5),
            ExpertAccess(1, "too-large", 11),
            ExpertAccess(2, "resident", 5),
        )
    )

    result = simulate_trace(trace, 10, CachePolicy.LRU)

    assert result.cache_misses == 2
    assert result.cache_hits == 1
    assert result.bypassed_accesses == 1
    assert result.evictions == 0
    assert result.final_resident_bytes == 5


def test_jsonl_trace_parser_accepts_multiple_experts_per_token() -> None:
    payload = "\n".join(
        [
            json.dumps(
                {"token_index": 0, "expert_id": "layer.0/expert.1", "size_bytes": 8}
            ),
            json.dumps(
                {"token_index": 0, "expert_id": "layer.0/expert.2", "size_bytes": 8}
            ),
            json.dumps(
                {"token_index": 1, "expert_id": "layer.0/expert.1", "size_bytes": 8}
            ),
        ]
    )

    trace = AccessTrace.from_jsonl(payload)

    assert len(trace.events) == 3
    assert trace.token_count == 2
    assert trace.expert_sizes["layer.0/expert.1"] == 8


@pytest.mark.parametrize(
    "payload",
    [
        "{invalid json}",
        json.dumps({"token_index": 0, "expert_id": "A"}),
        json.dumps({"token_index": -1, "expert_id": "A", "size_bytes": 1}),
        json.dumps({"token_index": 0, "expert_id": "", "size_bytes": 1}),
    ],
)
def test_jsonl_trace_parser_rejects_invalid_records(payload: str) -> None:
    with pytest.raises(TraceFormatError):
        AccessTrace.from_jsonl(payload)


def test_trace_rejects_non_monotonic_tokens_and_size_changes() -> None:
    with pytest.raises(ValueError, match="ordenados"):
        AccessTrace(
            (
                ExpertAccess(2, "A", 1),
                ExpertAccess(1, "B", 1),
            )
        )

    with pytest.raises(ValueError, match="tamanho"):
        AccessTrace(
            (
                ExpertAccess(0, "A", 1),
                ExpertAccess(1, "A", 2),
            )
        )


def test_synthetic_trace_is_reproducible_and_uses_top_k_accesses() -> None:
    first = generate_synthetic_trace(
        100,
        16,
        top_k=2,
        workload="phased",
        phase_tokens=20,
        seed=7,
    )
    second = generate_synthetic_trace(
        100,
        16,
        top_k=2,
        workload="phased",
        phase_tokens=20,
        seed=7,
    )

    assert first == second
    assert first.token_count == 100
    assert len(first.events) == 200
    assert first.has_uniform_expert_sizes


def test_uniform_workload_can_be_compared_with_belady() -> None:
    trace = generate_synthetic_trace(
        40,
        8,
        top_k=2,
        workload="uniform",
        seed=11,
    )

    results = compare_policies(trace, 16 * 1024 * 1024)

    assert len(results) == 4
    assert results[-1].policy == "belady_min"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"token_count": -1, "expert_count": 8},
        {"token_count": 10, "expert_count": 0},
        {"token_count": 10, "expert_count": 8, "top_k": 9},
        {"token_count": 10, "expert_count": 8, "hot_set_size": 1, "top_k": 2},
        {"token_count": 10, "expert_count": 8, "workload": "unknown"},
    ],
)
def test_synthetic_trace_rejects_invalid_parameters(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        generate_synthetic_trace(**kwargs)


def test_empty_trace_has_zero_rates() -> None:
    result = simulate_trace(AccessTrace(()), 1024, CachePolicy.LRU)

    assert result.total_accesses == 0
    assert result.hit_rate == 0
    assert result.miss_rate == 0
    assert result.bytes_read_per_token == 0
