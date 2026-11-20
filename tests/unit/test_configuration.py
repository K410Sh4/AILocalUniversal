import pytest

from storage.configuration import AppConfig, ConfigurationError, ConfigurationStore


def test_invalid_backend_url_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="URL"):
        AppConfig(base_url="localhost:11434").validate()


def test_malformed_ipv6_url_is_reported_as_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="URL"):
        AppConfig(base_url="http://[invalid").validate()


def test_config_file_is_written_with_private_permissions(tmp_path) -> None:
    path = tmp_path / "config.json"
    store = ConfigurationStore(path)
    store.save(AppConfig())

    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600
    assert store.load().base_url == "http://localhost:11434"



def test_embedding_model_is_optional_and_persisted(tmp_path) -> None:
    path = tmp_path / "config.json"
    store = ConfigurationStore(path)

    config = AppConfig(embedding_model="embeddinggemma")
    store.save(config)

    loaded = store.load()
    assert loaded.embedding_model == "embeddinggemma"


def test_legacy_configuration_without_embedding_model_remains_valid(tmp_path) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(
        '{"base_url":"http://localhost:11434","mode":"auto","keep_alive":"5m"}',
        encoding="utf-8",
    )

    assert ConfigurationStore(path).load().embedding_model is None


def test_blank_embedding_model_normalizes_to_none() -> None:
    config = AppConfig(embedding_model="   ")
    config.validate()

    assert config.embedding_model is None
