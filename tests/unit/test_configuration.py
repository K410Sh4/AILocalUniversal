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



def test_hardware_profile_and_protection_mode_are_persisted(tmp_path) -> None:
    path = tmp_path / "config.json"
    store = ConfigurationStore(path)
    config = AppConfig(
        hardware_profile="ultra_light",
        protection_mode="adaptive",
    )

    store.save(config)
    loaded = store.load()

    assert loaded.hardware_profile == "ultra_light"
    assert loaded.protection_mode == "adaptive"


def test_older_config_files_receive_safe_hardware_defaults(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"base_url": "http://localhost:11434"}', encoding="utf-8")

    loaded = ConfigurationStore(path).load()

    assert loaded.hardware_profile == "auto"
    assert loaded.protection_mode == "protected"


@pytest.mark.parametrize("field,value", [
    ("hardware_profile", "turbo"),
    ("protection_mode", "ignore_everything"),
    ("hardware_profile", []),
    ("protection_mode", None),
])
def test_invalid_hardware_policy_settings_are_rejected(field, value) -> None:
    config = AppConfig()
    setattr(config, field, value)

    with pytest.raises(ConfigurationError):
        config.validate()
