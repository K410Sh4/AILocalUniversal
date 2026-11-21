from engines.base import RunningModelSnapshot
from model_hub.contracts import ModelArtifact, ModelRecord
from resources.residency import ResidencyStatus, reconcile_model_residency


def _record(*, digest: str | None = "sha256:abc") -> ModelRecord:
    return ModelRecord(
        record_id="ollama:qwen3:4b",
        display_name="Qwen3 4B",
        family="qwen3",
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference="qwen3:4b",
                installed=True,
                digest=digest,
            ),
        ),
    )


def _snapshot(*, name: str = "qwen3:4b", digest: str | None = "sha256:abc"):
    return RunningModelSnapshot(name=name, model=name, digest=digest)


def test_residency_requires_exact_reference_and_digest_match() -> None:
    result = reconcile_model_residency(_record(), [_snapshot()])

    assert result.status is ResidencyStatus.CONFIRMED
    assert result.artifact_digest == result.resident_digest
    assert "Nenhuma dedução de memória" in result.reason


def test_residency_is_not_confirmed_when_either_digest_is_missing() -> None:
    result = reconcile_model_residency(_record(digest=None), [_snapshot()])

    assert result.status is ResidencyStatus.DIGEST_MISSING


def test_residency_is_not_confirmed_when_digest_differs() -> None:
    result = reconcile_model_residency(
        _record(), [_snapshot(digest="sha256:other")]
    )

    assert result.status is ResidencyStatus.DIGEST_MISMATCH


def test_residency_requires_exact_model_reference() -> None:
    result = reconcile_model_residency(
        _record(), [_snapshot(name="qwen3:4b-instruct")]
    )

    assert result.status is ResidencyStatus.NOT_RESIDENT


def test_residency_does_not_confirm_ambiguous_matches() -> None:
    result = reconcile_model_residency(
        _record(), [_snapshot(), _snapshot(name="qwen3:4b")]
    )

    assert result.status is ResidencyStatus.AMBIGUOUS


def test_residency_requires_installed_artifact_for_runtime() -> None:
    record = ModelRecord(
        record_id="ollama:qwen3:4b",
        display_name="Qwen3 4B",
        family="qwen3",
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference="qwen3:4b",
                installed=False,
                digest="sha256:abc",
            ),
        ),
    )

    result = reconcile_model_residency(record, [_snapshot()])

    assert result.status is ResidencyStatus.ARTIFACT_MISSING
