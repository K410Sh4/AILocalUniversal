"""Persistência atômica das configurações locais."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Configuração local inválida ou ilegível."""


def default_config_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "ailocal-universal" / "config.json"


def _atomic_json_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


@dataclass(slots=True)
class AppConfig:
    base_url: str = "http://localhost:11434"
    mode: str = "auto"
    preferred_model: str | None = None
    manual_model: str | None = None
    system_prompt: str = (
        "Você é o assistente do AILocal Universal. Responda em português claro, "
        "seja preciso e informe incertezas quando existirem."
    )
    keep_alive: str = "5m"
    embedding_model: str | None = None
    knowledge_enabled: bool = False
    resource_profile: str = "medium"

    def validate(self) -> None:
        if not isinstance(self.base_url, str):
            raise ConfigurationError("Endereço do Ollama precisa ser texto.")
        try:
            parsed = urlsplit(self.base_url)
        except ValueError as exc:
            raise ConfigurationError(f"URL do Ollama inválida: {exc}") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigurationError(
                "Endereço do Ollama inválido. Use uma URL http:// ou https://."
            )
        if not isinstance(self.mode, str) or self.mode not in {"auto", "manual"}:
            raise ConfigurationError("Modo de seleção inválido.")
        if self.preferred_model is not None and not isinstance(self.preferred_model, str):
            raise ConfigurationError("Modelo preferido precisa ser texto.")
        if self.manual_model is not None and not isinstance(self.manual_model, str):
            raise ConfigurationError("Modelo manual precisa ser texto.")
        if not isinstance(self.keep_alive, str) or not self.keep_alive.strip():
            raise ConfigurationError("keep_alive não pode ficar vazio.")
        if not isinstance(self.system_prompt, str):
            raise ConfigurationError("System prompt precisa ser texto.")
        if not isinstance(self.knowledge_enabled, bool):
            raise ConfigurationError("knowledge_enabled precisa ser booleano.")
        if (
            not isinstance(self.resource_profile, str)
            or self.resource_profile not in {"light", "medium", "ultra"}
        ):
            raise ConfigurationError(
                "resource_profile precisa ser light, medium ou ultra."
            )
        if self.embedding_model is not None and not isinstance(self.embedding_model, str):
            raise ConfigurationError("Modelo de embeddings precisa ser texto ou None.")
        if isinstance(self.embedding_model, str):
            self.embedding_model = self.embedding_model.strip() or None
        self.base_url = self.base_url.rstrip("/")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AppConfig:
        allowed = {
            "base_url",
            "mode",
            "preferred_model",
            "manual_model",
            "system_prompt",
            "keep_alive",
            "embedding_model",
            "knowledge_enabled",
            "resource_profile",
        }
        try:
            config = cls(**{key: value for key, value in payload.items() if key in allowed})
            config.validate()
            return config
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(f"Configuração inválida: {exc}") from exc


class ConfigurationStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Não foi possível ler {self.path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ConfigurationError("O arquivo de configuração deve conter um objeto JSON.")
        return AppConfig.from_dict(payload)

    def save(self, config: AppConfig) -> None:
        config.validate()
        _atomic_json_write(self.path, config.to_dict())
