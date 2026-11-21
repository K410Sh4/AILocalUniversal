"""Contratos versionáveis do catálogo de modelos."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

CATEGORIES = {
    "general", "coding", "reasoning", "vision", "audio", "speech",
    "embeddings", "reranking", "image_generation", "video_generation",
    "music_generation", "ocr", "object_detection", "translation", "agents", "multimodal", "unknown",
}
MODALITIES = {"text", "image", "audio", "video", "spatial", "unknown"}
METADATA_SOURCES = {"runtime_discovery", "user_curated", "catalog_import"}


def _positive(value: object, name: str) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
    ):
        raise ValueError(f"{name} precisa ser inteiro positivo ou None.")


def _url(value: str | None, name: str) -> None:
    if value is None:
        return
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} precisa ser URL HTTP(S).")


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    """Referência de um artefato em um runtime específico."""

    runtime: str
    reference: str
    installed: bool = False
    size_bytes: int | None = None
    digest: str | None = None
    quantization: str | None = None

    def __post_init__(self) -> None:
        if not self.runtime.strip() or len(self.runtime) > 48:
            raise ValueError("Runtime inválido.")
        if not self.reference.strip() or len(self.reference) > 512:
            raise ValueError("Referência inválida.")
        if not isinstance(self.installed, bool):
            raise ValueError("installed precisa ser booleano.")
        if self.size_bytes is not None and (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise ValueError("size_bytes precisa ser inteiro não negativo ou None.")
        if self.digest is not None and len(self.digest) > 256:
            raise ValueError("Digest muito longo.")
        if self.quantization is not None and len(self.quantization) > 64:
            raise ValueError("Quantização muito longa.")

    @classmethod
    def from_dict(cls, data: object) -> ModelArtifact:
        if not isinstance(data, dict):
            raise ValueError("Artefato precisa ser objeto.")
        return cls(
            runtime=str(data.get("runtime", "")),
            reference=str(data.get("reference", "")),
            installed=data.get("installed", False),
            size_bytes=data.get("size_bytes"),
            digest=data.get("digest"),
            quantization=data.get("quantization"),
        )


@dataclass(frozen=True, slots=True)
class ResourceRequirements:
    """Limites de execução documentados e auditáveis.

    Tamanho do arquivo em disco não é convertido em RAM/VRAM: pesos, cache KV,
    contexto, buffers e offload dependem do runtime e da configuração.
    """

    minimum_ram_bytes: int | None = None
    minimum_vram_bytes: int | None = None
    recommended_ram_bytes: int | None = None
    recommended_vram_bytes: int | None = None
    evidence_url: str | None = None
    verified: bool = False

    def __post_init__(self) -> None:
        for name in (
            "minimum_ram_bytes", "minimum_vram_bytes",
            "recommended_ram_bytes", "recommended_vram_bytes",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} precisa ser inteiro não negativo ou None.")
        if (
            self.minimum_ram_bytes is not None
            and self.recommended_ram_bytes is not None
            and self.recommended_ram_bytes < self.minimum_ram_bytes
        ):
            raise ValueError("RAM recomendada não pode ser menor que a mínima.")
        if (
            self.minimum_vram_bytes is not None
            and self.recommended_vram_bytes is not None
            and self.recommended_vram_bytes < self.minimum_vram_bytes
        ):
            raise ValueError("VRAM recomendada não pode ser menor que a mínima.")
        if not isinstance(self.verified, bool):
            raise ValueError("verified precisa ser booleano.")
        _url(self.evidence_url, "evidence_url")
        if self.verified and self.evidence_url is None:
            raise ValueError("Requisitos verificados precisam de URL de evidência.")
        if self.verified and (
            self.minimum_ram_bytes is None and self.minimum_vram_bytes is None
        ):
            raise ValueError("Requisitos verificados precisam de um limite mínimo.")

    @classmethod
    def from_dict(cls, data: object) -> ResourceRequirements:
        if not isinstance(data, dict):
            raise ValueError("Requisitos precisam ser objeto.")
        return cls(
            minimum_ram_bytes=data.get("minimum_ram_bytes"),
            minimum_vram_bytes=data.get("minimum_vram_bytes"),
            recommended_ram_bytes=data.get("recommended_ram_bytes"),
            recommended_vram_bytes=data.get("recommended_vram_bytes"),
            evidence_url=data.get("evidence_url"),
            verified=data.get("verified", False),
        )


@dataclass(frozen=True, slots=True)
class ModelRecord:
    """Ficha normalizada de um modelo, sem presumir dados ausentes."""

    record_id: str
    display_name: str
    family: str
    category: str = "unknown"
    capabilities: tuple[str, ...] = ()
    modalities: tuple[str, ...] = ("text",)
    architecture: str | None = None
    parameter_count: int | None = None
    active_parameter_count: int | None = None
    context_window: int | None = None
    license_name: str | None = None
    license_url: str | None = None
    license_verified: bool = False
    source_url: str | None = None
    publisher: str | None = None
    metadata_source: str = "runtime_discovery"
    resource_requirements: ResourceRequirements | None = None
    artifacts: tuple[ModelArtifact, ...] = ()
    kv_cache_bytes_per_token: int | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._:/+-]{0,191}", self.record_id):
            raise ValueError("record_id inválido.")
        for name in ("display_name", "family"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError(f"{name} precisa ser texto não vazio de até 200 caracteres.")
        if self.category not in CATEGORIES:
            raise ValueError(f"Categoria não suportada: {self.category}.")
        if self.metadata_source not in METADATA_SOURCES:
            raise ValueError("metadata_source inválida.")
        if not isinstance(self.capabilities, tuple) or any(
            not isinstance(item, str) or not item.strip() or len(item) > 64
            for item in self.capabilities
        ):
            raise ValueError("capabilities precisa ser tupla de textos curtos.")
        if not isinstance(self.modalities, tuple) or any(
            item not in MODALITIES for item in self.modalities
        ):
            raise ValueError("modalities contém modalidade não suportada.")
        for name in (
            "parameter_count", "active_parameter_count", "context_window",
            "kv_cache_bytes_per_token",
        ):
            _positive(getattr(self, name), name)
        if (
            self.parameter_count is not None
            and self.active_parameter_count is not None
            and self.active_parameter_count > self.parameter_count
        ):
            raise ValueError("Parâmetros ativos não podem exceder os totais.")
        if self.license_verified and (not self.license_name or not self.license_url):
            raise ValueError("Licença verificada precisa de identificação e fonte URL.")
        if not isinstance(self.license_verified, bool):
            raise ValueError("license_verified precisa ser booleano.")
        _url(self.license_url, "license_url")
        _url(self.source_url, "source_url")
        if self.publisher is not None and len(self.publisher) > 160:
            raise ValueError("publisher muito longo.")
        if len({(item.runtime, item.reference) for item in self.artifacts}) != len(
            self.artifacts
        ):
            raise ValueError("Artefatos duplicados.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> ModelRecord:
        if not isinstance(data, dict):
            raise ValueError("Registro de modelo precisa ser objeto.")
        caps = data.get("capabilities", [])
        mods = data.get("modalities", ["text"])
        artifacts = data.get("artifacts", [])
        if not isinstance(caps, (list, tuple)) or not isinstance(mods, (list, tuple)):
            raise ValueError("Capacidades e modalidades precisam ser listas.")
        if not isinstance(artifacts, (list, tuple)):
            raise ValueError("artifacts precisa ser lista.")
        requirements = data.get("resource_requirements")
        return cls(
            record_id=str(data.get("record_id", "")),
            display_name=str(data.get("display_name", "")),
            family=str(data.get("family", "")),
            category=str(data.get("category", "unknown")),
            capabilities=tuple(str(item) for item in caps),
            modalities=tuple(str(item) for item in mods),
            architecture=data.get("architecture"),
            parameter_count=data.get("parameter_count"),
            active_parameter_count=data.get("active_parameter_count"),
            context_window=data.get("context_window"),
            license_name=data.get("license_name"),
            license_url=data.get("license_url"),
            license_verified=data.get("license_verified", False),
            source_url=data.get("source_url"),
            publisher=data.get("publisher"),
            metadata_source=str(data.get("metadata_source", "runtime_discovery")),
            resource_requirements=(
                ResourceRequirements.from_dict(requirements)
                if requirements is not None else None
            ),
            artifacts=tuple(ModelArtifact.from_dict(item) for item in artifacts),
            kv_cache_bytes_per_token=data.get("kv_cache_bytes_per_token"),
        )
