import pytest

from model_hub.contracts import ModelArtifact, ModelRecord, ResourceRequirements


def test_model_record_round_trips_all_declared_metadata() -> None:
    record = ModelRecord(
        record_id="ollama:qwen3:4b",
        display_name="qwen3:4b",
        family="qwen3",
        category="general",
        capabilities=("chat", "streaming"),
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference="qwen3:4b",
                installed=True,
                size_bytes=1234,
                digest="sha256:abc",
            ),
        ),
    )
    assert ModelRecord.from_dict(record.to_dict()) == record


def test_resource_requirements_reject_recommended_lower_than_minimum() -> None:
    with pytest.raises(ValueError, match="RAM recomendada"):
        ResourceRequirements(
            minimum_ram_bytes=10,
            recommended_ram_bytes=9,
            verified=True,
            evidence_url="https://example.org/ram",
        )


def test_verified_resource_requirements_require_evidence() -> None:
    with pytest.raises(ValueError, match="URL de evidência"):
        ResourceRequirements(minimum_ram_bytes=10, verified=True)


def test_verified_license_requires_identifier_and_source() -> None:
    with pytest.raises(ValueError, match="Licença verificada"):
        ModelRecord(
            record_id="catalog:test",
            display_name="Test",
            family="Test",
            license_name="Apache-2.0",
            license_verified=True,
        )


def test_model_record_rejects_active_parameters_above_total() -> None:
    with pytest.raises(ValueError, match="Parâmetros ativos"):
        ModelRecord(
            record_id="catalog:moe",
            display_name="MoE",
            family="MoE",
            parameter_count=8_000_000_000,
            active_parameter_count=9_000_000_000,
        )


def test_artifact_rejects_negative_download_size() -> None:
    with pytest.raises(ValueError, match="size_bytes"):
        ModelArtifact(runtime="ollama", reference="model", size_bytes=-1)
