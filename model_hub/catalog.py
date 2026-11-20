"""Catálogo remoto curado e validação das referências instaláveis."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from importlib import resources
from urllib.parse import urlsplit

import httpx

CATALOG_SCHEMA_VERSION = 1
DEFAULT_REMOTE_URL = (
    "https://raw.githubusercontent.com/K410Sh4/AILocalUniversal/"
    "feature/neural-model-hub-v1/model_hub/catalog_default.json"
)
MAX_CATALOG_BYTES = 2 * 1024 * 1024

CATALOG_CATEGORIES: dict[str, str] = {
    "general": "LLMs e conversação",
    "coding": "Programação",
    "reasoning": "Raciocínio",
    "vision": "Visão computacional",
    "audio": "Áudio",
    "speech": "Áudio e voz",
    "embeddings": "Embeddings e RAG",
    "reranking": "Rerankers",
    "image_generation": "Geração de imagens",
    "video_generation": "Geração de vídeo",
    "music_generation": "Geração de música",
    "ocr": "OCR e documentos",
    "object_detection": "Detecção de objetos",
    "translation": "Tradução",
    "agents": "Agentes e ferramentas",
    "multimodal": "Multimodais",
}

_ALLOWED_PLATFORMS = {"linux", "macos", "windows"}
_MODEL_REFERENCE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}(?::[A-Za-z0-9._-]{1,64})?"
)


class CatalogError(ValueError):
    """Catálogo remoto ou embutido inválido."""


def current_platform() -> str:
    """Normaliza a plataforma do sistema para comparar requisitos do catálogo."""
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return "unknown"


def validate_model_reference(value: str) -> str:
    """Aceita apenas referências de modelo, nunca URLs ou comandos."""
    if not isinstance(value, str) or not _MODEL_REFERENCE.fullmatch(value):
        raise CatalogError("Referência de modelo Ollama inválida.")
    if ".." in value or value.endswith("/") or "//" in value:
        raise CatalogError("Referência de modelo Ollama inválida.")
    return value


def _validate_https_url(value: str, field_name: str, *, ollama_only: bool = False) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise CatalogError(f"{field_name} precisa ser uma URL HTTPS.")
    if ollama_only and not (
        parsed.hostname == "ollama.com" or parsed.hostname.endswith(".ollama.com")
    ):
        raise CatalogError(f"{field_name} precisa apontar para uma fonte oficial Ollama.")


@dataclass(frozen=True, slots=True)
class CatalogVariant:
    """Variante/tag exata que pode ser solicitada ao runtime."""

    reference: str
    size_bytes: int | None = None
    size_label: str | None = None
    quantization: str | None = None
    installable: bool = True
    supported_platforms: tuple[str, ...] = ("linux", "macos", "windows")
    install_note: str | None = None

    def __post_init__(self) -> None:
        validate_model_reference(self.reference)
        if self.size_bytes is not None and (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes <= 0
        ):
            raise CatalogError("size_bytes precisa ser inteiro positivo ou None.")
        if self.size_label is not None and len(self.size_label) > 100:
            raise CatalogError("size_label excede 100 caracteres.")
        if self.quantization is not None and len(self.quantization) > 64:
            raise CatalogError("Quantização excede 64 caracteres.")
        if not isinstance(self.installable, bool):
            raise CatalogError("installable precisa ser booleano.")
        if not self.supported_platforms or any(
            platform not in _ALLOWED_PLATFORMS for platform in self.supported_platforms
        ):
            raise CatalogError("Plataforma de instalação inválida.")
        if len(set(self.supported_platforms)) != len(self.supported_platforms):
            raise CatalogError("Plataformas de instalação duplicadas.")
        if self.install_note is not None and len(self.install_note) > 300:
            raise CatalogError("Nota de instalação excede 300 caracteres.")

    def available_on(self, platform: str | None = None) -> bool:
        target = platform or current_platform()
        return self.installable and target in self.supported_platforms

    @classmethod
    def from_dict(cls, payload: object) -> CatalogVariant:
        if not isinstance(payload, dict):
            raise CatalogError("Variante do catálogo precisa ser um objeto.")
        platforms = payload.get("supported_platforms", ["linux", "macos", "windows"])
        if not isinstance(platforms, list) or not all(
            isinstance(item, str) for item in platforms
        ):
            raise CatalogError("supported_platforms precisa ser uma lista de textos.")
        return cls(
            reference=str(payload.get("reference", "")),
            size_bytes=payload.get("size_bytes"),
            size_label=payload.get("size_label"),
            quantization=payload.get("quantization"),
            installable=payload.get("installable", True),
            supported_platforms=tuple(platforms),
            install_note=payload.get("install_note"),
        )


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Ficha pública curada, separada do inventário efetivamente instalado."""

    record_id: str
    display_name: str
    family: str
    summary: str
    publisher: str
    categories: tuple[str, ...]
    capabilities: tuple[str, ...]
    modalities: tuple[str, ...]
    source_url: str
    variants: tuple[CatalogVariant, ...]
    parameter_count: int | None = None
    active_parameter_count: int | None = None
    context_window: int | None = None
    license_name: str | None = None
    license_url: str | None = None
    license_verified: bool = False
    metadata_updated_at: str | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,191}", self.record_id):
            raise CatalogError("record_id do catálogo inválido.")
        for field_name in ("display_name", "family", "summary", "publisher"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip() or len(value) > 600:
                raise CatalogError(f"{field_name} precisa ser texto não vazio de até 600 caracteres.")
        if not self.categories or any(
            item not in CATALOG_CATEGORIES for item in self.categories
        ):
            raise CatalogError("A ficha contém categoria não suportada.")
        if len(set(self.categories)) != len(self.categories):
            raise CatalogError("A ficha contém categorias duplicadas.")
        if not self.variants:
            raise CatalogError("A ficha precisa oferecer ao menos uma variante.")
        if len({item.reference.casefold() for item in self.variants}) != len(self.variants):
            raise CatalogError("A ficha contém variantes duplicadas.")
        if any(not isinstance(item, str) or not item.strip() or len(item) > 64
               for item in self.capabilities):
            raise CatalogError("Capacidade inválida no catálogo.")
        if any(item not in {"text", "image", "audio", "video", "spatial"}
               for item in self.modalities):
            raise CatalogError("Modalidade inválida no catálogo.")
        for name in ("parameter_count", "active_parameter_count", "context_window"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
            ):
                raise CatalogError(f"{name} precisa ser inteiro positivo ou None.")
        if (
            self.parameter_count is not None
            and self.active_parameter_count is not None
            and self.active_parameter_count > self.parameter_count
        ):
            raise CatalogError("Parâmetros ativos não podem exceder os parâmetros totais.")
        if self.license_verified and (not self.license_name or not self.license_url):
            raise CatalogError("Licença verificada precisa de nome e fonte.")
        _validate_https_url(self.source_url, "source_url", ollama_only=True)
        if self.license_url is not None:
            _validate_https_url(self.license_url, "license_url")

    @classmethod
    def from_dict(cls, payload: object) -> CatalogEntry:
        if not isinstance(payload, dict):
            raise CatalogError("Ficha de catálogo precisa ser um objeto.")
        categories = payload.get("categories", [])
        capabilities = payload.get("capabilities", [])
        modalities = payload.get("modalities", ["text"])
        variants = payload.get("variants", [])
        if any(
            not isinstance(value, list)
            for value in (categories, capabilities, modalities, variants)
        ):
            raise CatalogError("Categorias, capacidades, modalidades e variantes precisam ser listas.")
        return cls(
            record_id=str(payload.get("record_id", "")),
            display_name=str(payload.get("display_name", "")),
            family=str(payload.get("family", "")),
            summary=str(payload.get("summary", "")),
            publisher=str(payload.get("publisher", "")),
            categories=tuple(str(item) for item in categories),
            capabilities=tuple(str(item) for item in capabilities),
            modalities=tuple(str(item) for item in modalities),
            source_url=str(payload.get("source_url", "")),
            variants=tuple(CatalogVariant.from_dict(item) for item in variants),
            parameter_count=payload.get("parameter_count"),
            active_parameter_count=payload.get("active_parameter_count"),
            context_window=payload.get("context_window"),
            license_name=payload.get("license_name"),
            license_url=payload.get("license_url"),
            license_verified=payload.get("license_verified", False),
            metadata_updated_at=payload.get("metadata_updated_at"),
        )


@dataclass(frozen=True, slots=True)
class CatalogDocument:
    catalog_version: str
    updated_at: str
    entries: tuple[CatalogEntry, ...]
    source: str
    warning: str | None = None


def parse_catalog(payload: object, *, source: str) -> CatalogDocument:
    if not isinstance(payload, dict) or payload.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise CatalogError("Versão de esquema do catálogo incompatível.")
    version = payload.get("catalog_version")
    updated_at = payload.get("updated_at")
    models = payload.get("models")
    if not isinstance(version, str) or not version.strip() or len(version) > 64:
        raise CatalogError("catalog_version ausente ou inválida.")
    if not isinstance(updated_at, str) or not updated_at.strip() or len(updated_at) > 64:
        raise CatalogError("updated_at ausente ou inválido.")
    if not isinstance(models, list) or len(models) > 1000:
        raise CatalogError("O catálogo precisa conter até 1000 modelos.")
    entries = tuple(CatalogEntry.from_dict(item) for item in models)
    ids = [entry.record_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise CatalogError("O catálogo contém record_id duplicado.")
    refs = [
        variant.reference.casefold()
        for entry in entries
        for variant in entry.variants
    ]
    if len(set(refs)) != len(refs):
        raise CatalogError("O catálogo contém referências de modelo duplicadas.")
    return CatalogDocument(
        catalog_version=version,
        updated_at=updated_at,
        entries=entries,
        source=source,
    )


class ModelCatalogClient:
    """Busca o catálogo versionado no GitHub e mantém fallback empacotado."""

    def __init__(
        self,
        *,
        remote_url: str = DEFAULT_REMOTE_URL,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.remote_url = remote_url
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def fetch(self) -> CatalogDocument:
        warning: str | None = None
        if self.remote_url:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout_seconds, connect=5.0),
                    follow_redirects=False,
                    transport=self.transport,
                ) as client:
                    response = await client.get(self.remote_url)
                    response.raise_for_status()
                    if len(response.content) > MAX_CATALOG_BYTES:
                        raise CatalogError("Catálogo remoto excede o limite de 2 MiB.")
                    return parse_catalog(response.json(), source="online")
            except (httpx.HTTPError, json.JSONDecodeError, CatalogError, TypeError) as exc:
                warning = f"Catálogo online indisponível: {exc}"

        try:
            raw = resources.files("model_hub").joinpath("catalog_default.json").read_text(
                encoding="utf-8"
            )
            document = parse_catalog(json.loads(raw), source="bundled")
        except (OSError, json.JSONDecodeError, CatalogError, TypeError) as exc:
            raise CatalogError(f"Falha no catálogo online e no catálogo local: {exc}") from exc

        return CatalogDocument(
            catalog_version=document.catalog_version,
            updated_at=document.updated_at,
            entries=document.entries,
            source=document.source,
            warning=warning,
        )
