import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from workflows.graph import GraphError, WorkflowGraph
from workflows.package_io import load_graph_from_package, save_graph_to_package


TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "workflows"
    / "multi_specialist.pipeline.graph.json"
)


def make_package(path: Path, *, signed=False) -> Path:
    manifest = {
        "format": "ailocal.neuralinjector",
        "format_version": "0.1.0",
        "package": {"id": "org.ailocal.test", "name": "Test", "version": "1.0.0", "kind": "workflow"},
        "compatibility": {
            "models": [
                {
                    "architecture": "qwen2",
                    "model_id": "qwen2.5:7b",
                    "match_policy": "architecture_compatible",
                },
                {
                    "architecture": "deepseek",
                    "model_id": "deepseek-r1:7b",
                    "match_policy": "architecture_compatible",
                },
                {
                    "architecture": "flux",
                    "model_id": "flux.1",
                    "match_policy": "architecture_compatible",
                },
            ],
            "engines": [{"id": "ollama"}, {"id": "image"}],
        },
        "components": {
            "plugins": [],
            "adapters": [],
            "transformations": [],
            "hardware_profiles": [],
            "pipelines": [],
            "grammars": [],
            "evaluations": [],
        },
        "integrity": {
            "algorithm": "sha256",
            "checksums_file": "security/checksums.sha256",
        },
    }
    if signed:
        manifest["signature"] = {
            "algorithm": "ed25519",
            "file": "security/signature.ed25519",
            "key_id": "test-key",
        }
    files = {
        "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode(),
        "plugins/readme.txt": b"test plugin content",
    }
    checksums = "\n".join(
        f"{hashlib.sha256(files[name]).hexdigest()}  {name}"
        for name in sorted(files)
    ) + "\n"
    files["security/checksums.sha256"] = checksums.encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return path


def test_save_and_load_graph_inside_neuralinjector_package(tmp_path):
    package = make_package(tmp_path / "test.neuralinjector")
    graph = WorkflowGraph.load(TEMPLATE)

    saved_path = save_graph_to_package(package, graph)
    loaded = load_graph_from_package(saved_path)

    assert loaded.graph_id == graph.graph_id
    assert loaded.to_dict() == graph.to_dict()

    with zipfile.ZipFile(saved_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert "graph/pipeline.graph.json" in manifest["components"]["pipelines"]
        checksums = archive.read("security/checksums.sha256").decode()
        assert "graph/pipeline.graph.json" in checksums


def test_tampered_package_file_is_rejected(tmp_path):
    package = make_package(tmp_path / "tampered.neuralinjector")
    graph = WorkflowGraph.load(TEMPLATE)
    save_graph_to_package(package, graph)

    with zipfile.ZipFile(package, "r") as source:
        files = {
            info.filename: source.read(info.filename)
            for info in source.infolist()
            if not info.is_dir()
        }
    files["plugins/readme.txt"] = b"tampered"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)

    with pytest.raises(GraphError) as exc_info:
        load_graph_from_package(package)

    assert exc_info.value.reason_code == "PACKAGE_CHECKSUM_MISMATCH"


def test_signed_package_is_not_modified_without_signing_key(tmp_path):
    package = make_package(tmp_path / "signed.neuralinjector", signed=True)
    graph = WorkflowGraph.load(TEMPLATE)

    with pytest.raises(GraphError) as exc_info:
        save_graph_to_package(package, graph)

    assert exc_info.value.reason_code == "SIGNED_PACKAGE_CANNOT_BE_MODIFIED"


def test_package_path_traversal_is_rejected(tmp_path):
    package = tmp_path / "unsafe.neuralinjector"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("../escape.txt", b"unsafe")

    graph = WorkflowGraph.load(TEMPLATE)
    with pytest.raises(GraphError) as exc_info:
        save_graph_to_package(package, graph)

    assert exc_info.value.reason_code == "UNSAFE_PACKAGE_PATH"
