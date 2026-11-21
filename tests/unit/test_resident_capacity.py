from datetime import UTC, datetime, timedelta

from engines.base import RunningModelSnapshot
from model_hub.contracts import ModelArtifact, ModelRecord
from model_hub.registry import ModelRegistry
from resources.manager import AdaptiveResourceManager
from resources.residency import (
    ResidentCapacityStatus,
    assess_resident_capacity,
)


def _record(*, digest: str | None = "sha256:abc", context_window: int = 32768):
    return ModelRecord(
        record_id="ollama:qwen3:4b",
        display_name="Qwen3 4B",
        family="qwen3",
        context_window=context_window,
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference="qwen3:4b",
                installed=True,
                digest=digest,
            ),
        ),
    )


def _snapshot(
    *,
    digest: str | None = "sha256:abc",
    size: int | None = 5 * 1024**3,
    vram: int | None = 3 * 1024**3,
    context: int | None = 8192,
    observed_at: str | None = None,
    expires_at: str | None = None,
    include_expiry: bool = True,
):
    observed = datetime.now(UTC)
    return RunningModelSnapshot(
        name="qwen3:4b",
        model="qwen3:4b",
        digest=digest,
        size_bytes=size,
        size_vram_bytes=vram,
        context_length=context,
        expires_at=(
            expires_at
            if expires_at is not None
            else (observed + timedelta(minutes=5)).isoformat()
            if include_expiry
            else None
        ),
        observed_at=observed_at or observed.isoformat(),
    )


def test_resident_capacity_reuses_runner_with_matching_digest_and_context() -> None:
    result = assess_resident_capacity(
        _record(),
        [_snapshot()],
        context_tokens=4096,
    )

    assert result.status is ResidentCapacityStatus.REUSE_READY
    assert result.incremental_runner_bytes == 0
    assert result.resident_total_bytes == 5 * 1024**3
    assert result.resident_vram_bytes == 3 * 1024**3
    assert result.resident_context_capacity_tokens == 8192
    assert "não são contabilizados novamente" in result.reason


def test_resident_capacity_requires_reload_when_context_is_larger() -> None:
    result = assess_resident_capacity(
        _record(),
        [_snapshot(context=4096)],
        context_tokens=8192,
    )

    assert result.status is ResidentCapacityStatus.CONTEXT_REQUIRES_RELOAD
    assert result.incremental_runner_bytes is None


def test_resident_capacity_rejects_context_above_model_window() -> None:
    result = assess_resident_capacity(
        _record(context_window=4096),
        [_snapshot(context=8192)],
        context_tokens=8192,
    )

    assert result.status is ResidentCapacityStatus.MODEL_CONTEXT_EXCEEDED


def test_resident_capacity_does_not_assume_concurrent_slots() -> None:
    result = assess_resident_capacity(
        _record(),
        [_snapshot()],
        context_tokens=4096,
        concurrent_requests=2,
    )

    assert result.status is ResidentCapacityStatus.CONCURRENCY_UNVERIFIED
    assert result.incremental_runner_bytes is None


def test_resident_capacity_falls_back_when_digest_is_not_confirmed() -> None:
    result = assess_resident_capacity(
        _record(),
        [_snapshot(digest="sha256:other")],
        context_tokens=4096,
    )

    assert result.status is ResidentCapacityStatus.IDENTITY_UNVERIFIED
    assert result.incremental_runner_bytes is None


def test_resident_capacity_rejects_incomplete_or_inconsistent_telemetry() -> None:
    missing = assess_resident_capacity(
        _record(),
        [_snapshot(vram=None)],
        context_tokens=4096,
    )
    inverted = assess_resident_capacity(
        _record(),
        [_snapshot(size=2 * 1024**3, vram=3 * 1024**3)],
        context_tokens=4096,
    )
    missing_context = assess_resident_capacity(
        _record(),
        [_snapshot(context=None)],
        context_tokens=4096,
    )

    assert missing.status is ResidentCapacityStatus.TELEMETRY_INCOMPLETE
    assert inverted.status is ResidentCapacityStatus.TELEMETRY_INCOMPLETE
    assert missing_context.status is ResidentCapacityStatus.TELEMETRY_INCOMPLETE


def test_resident_capacity_validates_context_and_concurrency_inputs() -> None:
    import pytest

    with pytest.raises(ValueError):
        assess_resident_capacity(_record(), [], context_tokens=True)
    with pytest.raises(ValueError):
        assess_resident_capacity(_record(), [], context_tokens=4096, concurrent_requests=0)



def test_resource_manager_exposes_resident_capacity_assessment(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry.json")
    record = _record()
    registry.upsert(record)

    result = AdaptiveResourceManager().assess_resident_capacity(
        record.record_id,
        registry,
        [_snapshot()],
        context_tokens=4096,
    )

    assert result.status is ResidentCapacityStatus.REUSE_READY
    assert result.incremental_runner_bytes == 0



def test_resident_capacity_rejects_stale_snapshot() -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    snapshot = _snapshot(
        observed_at=(now - timedelta(seconds=31)).isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    result = assess_resident_capacity(
        _record(),
        [snapshot],
        context_tokens=4096,
        now=now,
    )

    assert result.status is ResidentCapacityStatus.SNAPSHOT_STALE
    assert result.incremental_runner_bytes is None


def test_resident_capacity_rejects_expired_or_near_expiry_snapshot() -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    snapshot = _snapshot(
        observed_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=1)).isoformat(),
    )
    result = assess_resident_capacity(
        _record(),
        [snapshot],
        context_tokens=4096,
        now=now,
    )

    assert result.status is ResidentCapacityStatus.RESIDENCY_EXPIRED


def test_resident_capacity_requires_observation_and_expiry_timestamps() -> None:
    result = assess_resident_capacity(
        _record(),
        [_snapshot(include_expiry=False)],
        context_tokens=4096,
    )

    assert result.status is ResidentCapacityStatus.EXPIRY_UNVERIFIED
