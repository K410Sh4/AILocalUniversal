"""Registro local versionado do NeuralModel Hub."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import replace
from pathlib import Path

from engines.base import ModelInfo
from model_hub.contracts import ModelArtifact, ModelRecord

SCHEMA_VERSION = 1


class ModelRegistryError(ValueError):
    """Catálogo ausente, inválido ou incompatível."""


def default_registry_path() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "ailocal-universal" / "model-hub" / "registry.json"


def _category_for(model: ModelInfo) -> str:
    caps = model.capabilities
    if caps.embeddings:
        return "embeddings"
    if caps.vision:
        return "vision"
    if caps.chat:
        return "general"
    return "unknown"


def _capability_names(model: ModelInfo) -> tuple[str, ...]:
    caps = model.capabilities
    names = [
        name for name in ("chat", "streaming", "vision", "tool_calling", "embeddings")
        if getattr(caps, name, False)
    ]
    if not caps.verified:
        names.append("unverified")
    return tuple(names)


class ModelRegistry:
    """Armazena fichas locais; não baixa modelos nem inventa metadados.

    O inventário do runtime é uma observação local. Licença, arquitetura,
    quantização e requisitos de memória ficam desconhecidos até serem verificados.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_registry_path()
        self.load_warning: str | None = None
        self._persistence_enabled = True
        self._records: dict[str, ModelRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
                raise ModelRegistryError("Raiz ou versão de esquema do catálogo inválida.")
            raw = payload.get("records")
            if not isinstance(raw, list):
                raise ModelRegistryError("Catálogo precisa conter uma lista records.")
            loaded: dict[str, ModelRecord] = {}
            for item in raw:
                record = ModelRecord.from_dict(item)
                if record.record_id in loaded:
                    raise ModelRegistryError(f"ID duplicado: {record.record_id}")
                loaded[record.record_id] = record
            self._records = loaded
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self.load_warning = f"Catálogo não carregado; arquivo preservado: {exc}"
            self._persistence_enabled = False
            self._records = {}

    def _save(self) -> None:
        if not self._persistence_enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "records": [self._records[key].to_dict() for key in sorted(self._records)],
        }
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def list_records(
        self, *, category: str | None = None, installed_only: bool = False
    ) -> list[ModelRecord]:
        records = list(self._records.values())
        if category is not None:
            records = [item for item in records if item.category == category]
        if installed_only:
            records = [
                item for item in records
                if any(artifact.installed for artifact in item.artifacts)
            ]
        return sorted(records, key=lambda item: item.display_name.casefold())

    def get(self, record_id: str) -> ModelRecord | None:
        return self._records.get(record_id)

    def upsert(self, record: ModelRecord) -> None:
        self._records[record.record_id] = record
        self._save()

    def sync_runtime_inventory(
        self, runtime: str, models: list[ModelInfo]
    ) -> list[ModelRecord]:
        """Sincroniza inventário local sem sobrescrever metadados curados."""
        runtime = runtime.casefold()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._+-]{0,47}", runtime):
            raise ValueError("Runtime inválido.")
        updated = {
            key: replace(
                record,
                artifacts=tuple(
                    replace(artifact, installed=False)
                    if artifact.runtime == runtime else artifact
                    for artifact in record.artifacts
                ),
            )
            for key, record in self._records.items()
        }
        for model in models:
            name = model.name.strip()
            if not name:
                continue
            record_id = f"{runtime}:{name.casefold()}"
            existing = updated.get(record_id)
            previous_artifact = next(
                (
                    item for item in existing.artifacts
                    if item.runtime == runtime and item.reference == name
                ),
                None,
            ) if existing is not None else None
            artifact = ModelArtifact(
                runtime=runtime,
                reference=name,
                installed=True,
                size_bytes=model.size_bytes,
                digest=model.digest,
                quantization=model.quantization or (
                    previous_artifact.quantization if previous_artifact else None
                ),
            )
            if existing is None:
                modalities = ("text", "image") if model.capabilities.vision else ("text",)
                updated[record_id] = ModelRecord(
                    record_id=record_id,
                    display_name=name,
                    family=name.split(":", 1)[0],
                    category=_category_for(model),
                    capabilities=_capability_names(model),
                    modalities=modalities,
                    architecture=model.architecture,
                    parameter_count=model.parameter_count,
                    context_window=model.context_window,
                    kv_cache_bytes_per_token=model.kv_cache_bytes_per_token,
                    metadata_source="runtime_discovery",
                    artifacts=(artifact,),
                )
                continue
            artifacts = [
                item for item in existing.artifacts
                if not (item.runtime == runtime and item.reference == name)
            ]
            artifacts.append(artifact)
            existing = replace(
                existing,
                display_name=(
                    name if existing.metadata_source == "runtime_discovery"
                    else existing.display_name
                ),
                family=(
                    name.split(":", 1)[0]
                    if existing.metadata_source == "runtime_discovery"
                    else existing.family
                ),
                category=(
                    _category_for(model)
                    if existing.metadata_source == "runtime_discovery"
                    else existing.category
                ),
                capabilities=(
                    _capability_names(model)
                    if existing.metadata_source == "runtime_discovery"
                    else existing.capabilities
                ),
                modalities=(
                    ("text", "image") if model.capabilities.vision else ("text",)
                    if existing.metadata_source == "runtime_discovery"
                    else existing.modalities
                ),
                architecture=existing.architecture or model.architecture,
                parameter_count=existing.parameter_count or model.parameter_count,
                context_window=existing.context_window or model.context_window,
                kv_cache_bytes_per_token=(
                    existing.kv_cache_bytes_per_token or model.kv_cache_bytes_per_token
                ),
                artifacts=tuple(artifacts),
            )
            updated[record_id] = existing
        self._records = updated
        self._save()
        return self.list_records(installed_only=True)

    def reload(self) -> None:
        self.load_warning = None
        self._persistence_enabled = True
        self._records = {}
        self._load()
