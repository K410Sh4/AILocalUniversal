from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

from kia_bridge import KiaMemoryError, KiaMemoryStore, KiaRuntimeClient


def sample_network(version: int = 3) -> dict:
    return {
        "capabilities": {},
        "components": {},
        "connections": [],
        "feedback_history": [],
        "version": version,
    }


def fake_host(path: Path, log_path: Path) -> list[str]:
    path.write_text(
        """#!/usr/bin/env python3
import json
import sys

state = None
restored = None
log_path = sys.argv[1]

for line in sys.stdin:
    request = json.loads(line)
    command = request["command"]
    kind = command["type"]
    with open(log_path, "a", encoding="utf-8") as stream:
        stream.write(kind + "\\n")

    if kind == "health":
        result = {
            "service": "kia-cognitive-runtime",
            "version": "0.4.0",
            "protocol_version": 2
        }
    elif kind == "restore_learning":
        restored = command["payload"]["network"]
        result = {"network_version": restored["version"]}
    elif kind == "replace_state":
        state = command["payload"]["state"]
        if restored is not None:
            state["network"]["feedback_history"] = restored["feedback_history"]
            state["network"]["version"] = max(
                state["network"]["version"], restored["version"]
            )
        result = {"network_version": state["network"]["version"]}
    elif kind == "export_network":
        result = {"network": state["network"]}
    elif kind == "record_feedback":
        result = {"updated_weight": 0.9, "observations": 1}
    elif kind == "shutdown":
        result = {"shutdown": True}
    else:
        result = {}

    print(json.dumps({
        "protocol_version": 2,
        "request_id": request["request_id"],
        "ok": True,
        "result": result
    }), flush=True)
    if kind == "shutdown":
        break
""",
        encoding="utf-8",
    )
    path.chmod(0o700)
    return [sys.executable, str(path), str(log_path)]


def test_memory_store_round_trips_snapshots_and_appends_metadata_only_events(
    tmp_path: Path,
) -> None:
    database = tmp_path / "private" / "memory.sqlite3"
    network = sample_network()

    with KiaMemoryStore(database) as store:
        assert store.load_network() is None
        store.save_network(network, event_type="network_synced")
        store.save_network(network, event_type="feedback_applied")
        assert store.load_network() == network
        events = store.list_events(limit=10)
        assert [event["event_type"] for event in events] == [
            "feedback_applied",
            "network_synced",
        ]
        assert events[0]["summary"]["feedback_count"] == 0

    if os.name == "posix":
        assert database.stat().st_mode & 0o777 == 0o600
        assert database.parent.stat().st_mode & 0o777 == 0o700


def test_memory_store_rejects_corrupted_snapshot_hash(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    with KiaMemoryStore(database) as store:
        store.save_network(sample_network())

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE cognitive_snapshots SET payload_sha256 = ?",
        ("0" * 64,),
    )
    connection.commit()
    connection.close()

    with KiaMemoryStore(database) as store:
        with pytest.raises(KiaMemoryError, match="Hash do snapshot"):
            store.load_network()


def test_memory_store_rejects_invalid_network_contract(tmp_path: Path) -> None:
    with KiaMemoryStore(tmp_path / "memory.sqlite3") as store:
        with pytest.raises(KiaMemoryError, match="Snapshot não contém"):
            store.save_network({"version": 1})


def test_runtime_client_persists_network_and_feedback_events(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    store = KiaMemoryStore(database)
    log = tmp_path / "host.log"
    command = fake_host(tmp_path / "fake-host.py", log)
    network = sample_network(version=7)

    with KiaRuntimeClient(command, timeout_seconds=2.0, memory_store=store) as client:
        client.replace_state({"network": network, "available_executors": []})
        client.record_feedback(
            {
                "capability_id": "reasoning",
                "component_id": "local-model",
                "outcome": "success",
                "validation_ref": "independent-test-1",
                "notes": "validated",
            }
        )

    commands = log.read_text(encoding="utf-8").splitlines()
    assert commands == [
        "health",
        "replace_state",
        "export_network",
        "record_feedback",
        "export_network",
        "shutdown",
    ]
    assert store.load_network() == network
    assert store.list_events(limit=10)[0]["event_type"] == "feedback_applied"
    store.close()


def test_runtime_client_restores_persisted_network_before_fresh_state(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    store = KiaMemoryStore(database)
    persisted = sample_network(version=11)
    persisted["feedback_history"] = [
        {
            "capability_id": "reasoning",
            "component_id": "local-model",
            "outcome": "success",
            "validation_ref": "persisted-validation",
            "notes": None,
        }
    ]
    store.save_network(persisted)

    log = tmp_path / "second-host.log"
    command = fake_host(tmp_path / "second-host.py", log)
    with KiaRuntimeClient(command, timeout_seconds=2.0, memory_store=store) as client:
        client.replace_state(
            {"network": sample_network(version=1), "available_executors": []}
        )

    commands = log.read_text(encoding="utf-8").splitlines()
    assert commands[:4] == [
        "health",
        "restore_learning",
        "replace_state",
        "export_network",
    ]
    restored = store.load_network()
    assert restored is not None
    assert restored["version"] == 11
    assert restored["feedback_history"] == persisted["feedback_history"]
    store.close()


def test_memory_database_rejects_chat_and_document_payload_fields(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    unsafe = sample_network()
    unsafe["components"] = {
        "component-1": {
            "id": "component-1",
            "metadata": {"prompt": "PRIVATE_CHAT_PROMPT_DO_NOT_PERSIST"},
        }
    }
    with KiaMemoryStore(database) as store:
        with pytest.raises(KiaMemoryError, match="conteúdo conversacional"):
            store.save_network(unsafe)
        store.save_network(sample_network())

    raw_database = database.read_bytes()
    assert b"PRIVATE_CHAT_PROMPT_DO_NOT_PERSIST" not in raw_database
    connection = sqlite3.connect(database)
    event_payloads = [
        row[0] for row in connection.execute("SELECT payload_json FROM cognitive_events")
    ]
    connection.close()
    assert event_payloads
    assert "PRIVATE_CHAT_PROMPT_DO_NOT_PERSIST" not in json.dumps(event_payloads)


def test_memory_store_strips_free_text_feedback_notes(tmp_path: Path) -> None:
    network = sample_network(version=4)
    network["feedback_history"] = [
        {
            "capability_id": "reasoning",
            "component_id": "local-model",
            "outcome": "success",
            "validation_ref": "independent-validation-4",
            "notes": "PRIVATE_CHAT_PROMPT_DO_NOT_PERSIST",
        }
    ]

    with KiaMemoryStore(tmp_path / "memory.sqlite3") as store:
        store.save_network(network)
        persisted = store.load_network()

    assert persisted is not None
    assert persisted["feedback_history"][0]["notes"] is None


@pytest.mark.skipif(os.name != "posix", reason="Permissões POSIX não se aplicam.")
def test_custom_existing_directory_permissions_are_not_modified(tmp_path: Path) -> None:
    directory = tmp_path / "caller-owned"
    directory.mkdir()
    directory.chmod(0o750)
    with KiaMemoryStore(directory / "memory.sqlite3"):
        pass
    assert directory.stat().st_mode & 0o777 == 0o750
