"""Safe read/update helpers for pipeline graphs inside .neuralinjector ZIP packages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from workflows.graph import GraphError, WorkflowGraph


GRAPH_PATH = "graph/pipeline.graph.json"
MANIFEST_PATH = "manifest.json"
MAX_ARCHIVE_ENTRIES = 20_000
MAX_ENTRY_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024


class PackageGraphError(GraphError):
    """Safe package graph import/export failure."""


def _safe_archive_path(name: str) -> None:
    if (
        not name
        or "\\" in name
        or name.startswith("/")
        or re.match(r"^[A-Za-z]:", name)
        or "\x00" in name
    ):
        raise PackageGraphError("UNSAFE_PACKAGE_PATH", f"Caminho inválido no pacote: {name!r}.")
    raw_parts = name.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise PackageGraphError("UNSAFE_PACKAGE_PATH", f"Caminho inseguro no pacote: {name!r}.")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise PackageGraphError("UNSAFE_PACKAGE_PATH", f"Caminho inseguro no pacote: {name!r}.")


def _read_package(path: Path) -> dict[str, bytes]:
    if not path.is_file():
        raise PackageGraphError("PACKAGE_NOT_FOUND", f"Pacote não encontrado: {path}.")
    if path.suffix.lower() != ".neuralinjector":
        raise PackageGraphError(
            "INVALID_PACKAGE_EXTENSION",
            "Selecione um arquivo .neuralinjector.",
        )

    files: dict[str, bytes] = {}
    total = 0
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise PackageGraphError(
                    "PACKAGE_TOO_MANY_ENTRIES",
                    "O pacote excede o limite de arquivos permitido.",
                )
            for info in infos:
                normalized_name = info.filename.rstrip("/") if info.is_dir() else info.filename
                _safe_archive_path(normalized_name)
                if info.is_dir():
                    continue
                if info.filename in files:
                    raise PackageGraphError(
                        "PACKAGE_DUPLICATE_PATH",
                        f"O pacote contém caminho duplicado: {info.filename}.",
                    )
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise PackageGraphError(
                        "PACKAGE_SYMLINK_REJECTED",
                        f"Links simbólicos não são aceitos: {info.filename}.",
                    )
                if info.file_size > MAX_ENTRY_BYTES:
                    raise PackageGraphError(
                        "PACKAGE_ENTRY_TOO_LARGE",
                        f"Arquivo excede o limite: {info.filename}.",
                    )
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    raise PackageGraphError(
                        "PACKAGE_TOO_LARGE",
                        "O conteúdo descompactado excede o limite total do pacote.",
                    )
                files[info.filename] = archive.read(info)
    except zipfile.BadZipFile as exc:
        raise PackageGraphError(
            "INVALID_PACKAGE_ZIP",
            "O arquivo .neuralinjector está corrompido.",
        ) from exc
    except OSError as exc:
        raise PackageGraphError(
            "PACKAGE_READ_ERROR",
            f"Não foi possível ler o pacote: {exc}",
        ) from exc
    return files


def _manifest(files: dict[str, bytes]) -> dict[str, Any]:
    raw = files.get(MANIFEST_PATH)
    if raw is None:
        raise PackageGraphError("PACKAGE_MANIFEST_MISSING", "O pacote não contém manifest.json.")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageGraphError(
            "PACKAGE_MANIFEST_INVALID",
            "manifest.json não é JSON UTF-8 válido.",
        ) from exc
    if not isinstance(manifest, dict) or manifest.get("format") != "ailocal.neuralinjector":
        raise PackageGraphError(
            "PACKAGE_FORMAT_INVALID",
            "O manifesto não identifica um NeuralInjector Package.",
        )
    if manifest.get("signature"):
        raise PackageGraphError(
            "SIGNED_PACKAGE_CANNOT_BE_MODIFIED",
            "Este pacote possui assinatura. Alterá-lo invalidaria a assinatura Ed25519.",
            ("Exporte uma cópia sem assinatura ou implemente assinatura com uma chave confiável.",),
        )
    components = manifest.get("components")
    integrity = manifest.get("integrity")
    if not isinstance(components, dict) or not isinstance(components.get("pipelines"), list):
        raise PackageGraphError(
            "PACKAGE_PIPELINES_INVALID",
            "manifest.json precisa declarar components.pipelines como lista.",
        )
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256":
        raise PackageGraphError(
            "PACKAGE_INTEGRITY_INVALID",
            "O manifesto precisa declarar integridade SHA-256.",
        )
    checksum_path = integrity.get("checksums_file")
    if not isinstance(checksum_path, str):
        raise PackageGraphError(
            "PACKAGE_CHECKSUMS_PATH_INVALID",
            "O manifesto não declarou o caminho de checksums.",
        )
    _safe_archive_path(checksum_path)
    return manifest


def _validate_graph_manifest_references(
    graph: WorkflowGraph,
    manifest: dict[str, Any],
) -> None:
    compatibility = manifest.get("compatibility", {})
    if not isinstance(compatibility, dict):
        raise PackageGraphError(
            "PACKAGE_COMPATIBILITY_INVALID",
            "compatibility precisa ser um objeto no manifesto.",
        )
    declared_models = {
        item.get("model_id")
        for item in compatibility.get("models", [])
        if isinstance(item, dict) and isinstance(item.get("model_id"), str)
    }
    declared_engines = {
        item.get("id")
        for item in compatibility.get("engines", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    declared_plugins = {
        item.get("id")
        for item in manifest.get("components", {}).get("plugins", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    for node in graph.nodes:
        if not node.enabled or not node.node_type.startswith("specialist."):
            continue
        model_id = node.config.get("model_id")
        engine_id = node.config.get("engine")
        if model_id not in declared_models:
            raise PackageGraphError(
                "MODEL_REFERENCE_NOT_DECLARED",
                f"O modelo '{model_id}' do nó '{node.label}' não está declarado "
                "em compatibility.models.",
                ("Adicione o model_id ao manifesto antes de salvar o NeuralMap no pacote.",),
            )
        if engine_id not in declared_engines:
            raise PackageGraphError(
                "ENGINE_REFERENCE_NOT_DECLARED",
                f"O engine '{engine_id}' do nó '{node.label}' não está declarado "
                "em compatibility.engines.",
                ("Declare o backend requerido no manifesto do pacote.",),
            )
        plugin_ref = node.config.get("plugin_ref")
        if plugin_ref and plugin_ref not in declared_plugins:
            raise PackageGraphError(
                "PLUGIN_REFERENCE_NOT_DECLARED",
                f"O NeuralPlugin '{plugin_ref}' do nó '{node.label}' não está "
                "declarado em components.plugins.",
                ("Instale/declare o plugin no manifesto ou remova a referência do nó.",),
            )
        if node.node_type == "hardware.profile":
            profile_id = node.config.get("profile", "auto")
            if profile_id != "auto":
                profile_path = f"hardware/profiles/{profile_id}.json"
                declared_profiles = manifest.get("components", {}).get(
                    "hardware_profiles", []
                )
                if profile_path not in declared_profiles:
                    raise PackageGraphError(
                        "HARDWARE_PROFILE_NOT_DECLARED",
                        f"O perfil '{profile_id}' do nó '{node.label}' não está declarado no pacote.",
                        ("Adicione o arquivo do perfil em components.hardware_profiles.",),
                    )


def _checksum_content(files: dict[str, bytes], checksum_path: str) -> bytes:
    lines = []
    for name in sorted(files):
        if name == checksum_path:
            continue
        digest = hashlib.sha256(files[name]).hexdigest()
        lines.append(f"{digest}  {name}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _verify_checksums(files: dict[str, bytes], checksum_path: str) -> None:
    raw = files.get(checksum_path)
    if raw is None:
        raise PackageGraphError(
            "PACKAGE_CHECKSUMS_MISSING",
            f"O arquivo de integridade '{checksum_path}' não existe.",
        )
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise PackageGraphError(
            "PACKAGE_CHECKSUMS_INVALID",
            "O arquivo de checksums não é UTF-8 válido.",
        ) from exc

    verified: set[str] = set()
    for line in lines:
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64:
            raise PackageGraphError(
                "PACKAGE_CHECKSUMS_INVALID",
                "Linha inválida no arquivo de checksums SHA-256.",
            )
        _safe_archive_path(name)
        if name == checksum_path or name not in files:
            raise PackageGraphError(
                "PACKAGE_CHECKSUMS_INVALID",
                f"Entrada de checksum inesperada: {name}.",
            )
        actual = hashlib.sha256(files[name]).hexdigest()
        if actual.lower() != digest.lower():
            raise PackageGraphError(
                "PACKAGE_CHECKSUM_MISMATCH",
                f"A integridade do arquivo '{name}' não confere.",
                ("Reimporte uma cópia íntegra do pacote.",),
            )
        verified.add(name)

    expected = set(files) - {checksum_path}
    missing = expected - verified
    if missing:
        raise PackageGraphError(
            "PACKAGE_CHECKSUMS_INCOMPLETE",
            "O arquivo de checksums não cobre todos os arquivos do pacote: "
            + ", ".join(sorted(missing)[:8]),
        )


def _write_package(path: Path, files: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    os.close(fd)
    try:
        with zipfile.ZipFile(
            temporary_name,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for name in sorted(files):
                _safe_archive_path(name)
                archive.writestr(name, files[name])
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def save_graph_to_package(
    package_path: str | Path,
    graph: WorkflowGraph,
    *,
    graph_path: str = GRAPH_PATH,
) -> Path:
    """Atomically add/update a graph and manifest reference in an unsigned package."""
    graph_data = graph.to_dict()
    validated_graph = WorkflowGraph.from_dict(graph_data)
    _safe_archive_path(graph_path)
    if graph_path != GRAPH_PATH:
        raise PackageGraphError(
            "UNSUPPORTED_GRAPH_PATH",
            f"Na NIP 0.1.0 o grafo deve ser salvo em {GRAPH_PATH}.",
        )
    if (
        graph_path in {MANIFEST_PATH, "security/checksums.sha256"}
        or graph_path.startswith("security/")
    ):
        raise PackageGraphError(
            "RESERVED_PACKAGE_PATH",
            "O caminho do grafo não pode sobrescrever manifesto, checksums "
            "ou arquivos de segurança.",
        )
    path = Path(package_path).expanduser().resolve()
    files = _read_package(path)
    manifest = _manifest(files)
    checksum_path = manifest["integrity"]["checksums_file"]
    _verify_checksums(files, checksum_path)
    _validate_graph_manifest_references(validated_graph, manifest)

    if graph_path == checksum_path:
        raise PackageGraphError(
            "RESERVED_PACKAGE_PATH",
            "O caminho do grafo não pode sobrescrever o arquivo de checksums.",
        )
    pipelines = manifest["components"]["pipelines"]
    if graph_path not in pipelines:
        pipelines.append(graph_path)
    files[graph_path] = (
        json.dumps(graph_data, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    files[MANIFEST_PATH] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    files[checksum_path] = _checksum_content(files, checksum_path)
    _write_package(path, files)
    return path


def load_graph_from_package(
    package_path: str | Path,
    *,
    graph_path: str = GRAPH_PATH,
) -> WorkflowGraph:
    """Load only a graph explicitly referenced by the package manifest."""
    _safe_archive_path(graph_path)
    files = _read_package(Path(package_path).expanduser().resolve())
    manifest = _manifest(files)
    checksum_path = manifest["integrity"]["checksums_file"]
    _verify_checksums(files, checksum_path)
    if graph_path not in manifest["components"]["pipelines"]:
        raise PackageGraphError(
            "GRAPH_NOT_DECLARED_IN_MANIFEST",
            "O grafo não está declarado em components.pipelines.",
        )
    raw = files.get(graph_path)
    if raw is None:
        raise PackageGraphError(
            "GRAPH_FILE_MISSING",
            f"O manifesto referencia {graph_path}, mas o arquivo não existe.",
        )
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageGraphError("GRAPH_JSON_INVALID", "O pipeline.graph.json é inválido.") from exc
    graph = WorkflowGraph.from_dict(data)
    _validate_graph_manifest_references(graph, manifest)
    return graph
