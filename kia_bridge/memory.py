"""Memória cognitiva persistente local da K.IA.

Guarda snapshots de rede e metadados de eventos. Não armazena prompts, respostas
ou conteúdo documental.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_EVENTS = 10_000
DEFAULT_NAMESPACE = "default"


class KiaMemoryError(RuntimeError):
    """Falha de integridade, esquema ou persistência da memória cognitiva."""


def default_kia_memory_path() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "ailocal-universal" / "kia" / "cognitive-memory.sqlite3"


def _canonical_json(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise KiaMemoryError("Snapshot cognitivo não pode ser serializado com segurança.") from exc


class KiaMemoryStore:
    """Snapshot transacional e event log limitado, privado e validado por hash."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> None:
        if not isinstance(namespace, str) or not namespace.strip() or len(namespace) > 128:
            raise ValueError("namespace da memória precisa ser texto não vazio (até 128 chars).")
        self.path = Path(path).expanduser() if path is not None else default_kia_memory_path()
        self.namespace = namespace.strip()
        if path is None:
            app_data_directory = self.path.parent.parent
            app_data_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(app_data_directory, 0o700)
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.path.parent, 0o700)
        else:
            parent_existed = self.path.parent.exists()
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not parent_existed:
                os.chmod(self.path.parent, 0o700)
        self._lock = threading.RLock()
        self._closed = False
        try:
            self._connection = sqlite3.connect(
                self.path,
                timeout=5.0,
                isolation_level=None,
                check_same_thread=False,
            )
            self._connection.execute("PRAGMA journal_mode=DELETE")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA secure_delete=ON")
            self._initialize()
            os.chmod(self.path, 0o600)
        except KiaMemoryError:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            raise
        except (OSError, sqlite3.Error) as exc:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            raise KiaMemoryError(f"Não foi possível inicializar a memória K.IA: {exc}") from exc

    def _initialize(self) -> None:
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise KiaMemoryError(
                f"Banco de memória versão {version} é mais novo que a suportada {SCHEMA_VERSION}."
            )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cognitive_snapshots (
                    namespace TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    network_version INTEGER NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cognitive_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    namespace TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    network_version INTEGER NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cognitive_events_namespace "
                "ON cognitive_events(namespace, sequence DESC)"
            )
            self._connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            self._connection.execute("COMMIT")
        except sqlite3.Error:
            self._connection.execute("ROLLBACK")
            raise

    @staticmethod
    def _validate_network(
        network: dict[str, Any],
        *,
        allow_free_text_notes: bool = False,
    ) -> int:
        if not isinstance(network, dict):
            raise KiaMemoryError("Snapshot da rede precisa ser um objeto.")
        required = ("capabilities", "components", "connections", "feedback_history", "version")
        if any(key not in network for key in required):
            raise KiaMemoryError("Snapshot não contém todos os campos da rede cognitiva.")
        if (
            not isinstance(network["capabilities"], dict)
            or not isinstance(network["components"], dict)
        ):
            raise KiaMemoryError("Capacidades e componentes precisam ser objetos.")
        if (
            not isinstance(network["connections"], list)
            or not isinstance(network["feedback_history"], list)
        ):
            raise KiaMemoryError("Conexões e feedback precisam ser listas.")
        version = network["version"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise KiaMemoryError("Versão da rede no snapshot é inválida.")

        forbidden_keys = {
            "prompt",
            "raw_prompt",
            "user_input",
            "input_payload",
            "conversation",
            "messages",
            "document_text",
            "raw_content",
        }

        def reject_user_payload(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if str(key).casefold() in forbidden_keys:
                        raise KiaMemoryError(
                            "Snapshot contém campo de conteúdo conversacional/documental proibido."
                        )
                    reject_user_payload(item)
            elif isinstance(value, list):
                for item in value:
                    reject_user_payload(item)

        reject_user_payload(network)
        for feedback in network["feedback_history"]:
            if not isinstance(feedback, dict):
                raise KiaMemoryError("Registro de feedback persistido precisa ser objeto.")
            if (
                feedback.get("notes") not in (None, "")
                and not allow_free_text_notes
            ):
                raise KiaMemoryError("Notas livres não podem ser persistidas na memória cognitiva.")
        return version

    def load_network(self) -> dict[str, Any] | None:
        with self._lock:
            if self._closed:
                raise KiaMemoryError("Memória K.IA já foi encerrada.")
            try:
                row = self._connection.execute(
                    "SELECT schema_version, payload_sha256, payload_json "
                    "FROM cognitive_snapshots WHERE namespace = ?",
                    (self.namespace,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise KiaMemoryError(f"Falha ao ler snapshot da memória K.IA: {exc}") from exc
        if row is None:
            return None
        schema_version, expected_digest, payload_json = row
        if schema_version != SCHEMA_VERSION:
            raise KiaMemoryError(
                f"Snapshot usa esquema {schema_version}; suportado {SCHEMA_VERSION}."
            )
        actual_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(expected_digest, actual_digest):
            raise KiaMemoryError("Hash do snapshot cognitivo diverge; restauração bloqueada.")
        try:
            network = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            raise KiaMemoryError("Snapshot da memória contém JSON inválido.") from exc
        if not isinstance(network, dict):
            raise KiaMemoryError("Snapshot da rede não é um objeto JSON.")
        self._validate_network(network)
        return network

    def save_network(
        self,
        network: dict[str, Any],
        *,
        event_type: str = "network_synced",
    ) -> None:
        if event_type not in {"network_synced", "feedback_applied", "network_restored"}:
            raise ValueError("event_type de memória não reconhecido.")
        # Remove notas livres antes da validação e da serialização; pesos e
        # referências estruturadas permanecem disponíveis para restaurar a plasticidade.
        self._validate_network(network, allow_free_text_notes=True)
        persisted_network = json.loads(_canonical_json(network))
        for feedback in persisted_network["feedback_history"]:
            feedback["notes"] = None
        version = self._validate_network(persisted_network)
        payload_json = _canonical_json(persisted_network)
        digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        now = datetime.now(UTC).isoformat()
        event_json = _canonical_json(
            {
                "capability_count": len(network["capabilities"]),
                "component_count": len(network["components"]),
                "connection_count": len(network["connections"]),
                "feedback_count": len(network["feedback_history"]),
                "snapshot_sha256": digest,
            }
        )
        with self._lock:
            if self._closed:
                raise KiaMemoryError("Memória K.IA já foi encerrada.")
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    """
                    INSERT INTO cognitive_snapshots(
                        namespace, schema_version, network_version, payload_sha256,
                        payload_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(namespace) DO UPDATE SET
                        schema_version=excluded.schema_version,
                        network_version=excluded.network_version,
                        payload_sha256=excluded.payload_sha256,
                        payload_json=excluded.payload_json,
                        updated_at=excluded.updated_at
                    """,
                    (self.namespace, SCHEMA_VERSION, version, digest, payload_json, now),
                )
                self._connection.execute(
                    """
                    INSERT INTO cognitive_events(
                        event_id, namespace, event_type, network_version,
                        payload_sha256, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        self.namespace,
                        event_type,
                        version,
                        hashlib.sha256(event_json.encode("utf-8")).hexdigest(),
                        event_json,
                        now,
                    ),
                )
                self._connection.execute(
                    """
                    DELETE FROM cognitive_events
                    WHERE namespace = ? AND sequence NOT IN (
                        SELECT sequence FROM cognitive_events
                        WHERE namespace = ? ORDER BY sequence DESC LIMIT ?
                    )
                    """,
                    (self.namespace, self.namespace, MAX_EVENTS),
                )
                self._connection.execute("COMMIT")
                os.chmod(self.path, 0o600)
            except (sqlite3.Error, OSError) as exc:
                try:
                    self._connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise KiaMemoryError(f"Falha ao persistir a rede cognitiva: {exc}") from exc

    def list_events(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit precisa estar entre 1 e 1000.")
        with self._lock:
            if self._closed:
                raise KiaMemoryError("Memória K.IA já foi encerrada.")
            try:
                rows = self._connection.execute(
                    """
                    SELECT sequence, event_id, event_type, network_version,
                           payload_json, created_at
                    FROM cognitive_events WHERE namespace = ?
                    ORDER BY sequence DESC LIMIT ?
                    """,
                    (self.namespace, limit),
                ).fetchall()
            except sqlite3.Error as exc:
                raise KiaMemoryError(f"Falha ao consultar eventos cognitivos: {exc}") from exc
        return [
            {
                "sequence": row[0],
                "event_id": row[1],
                "event_type": row[2],
                "network_version": row[3],
                "summary": json.loads(row[4]),
                "created_at": row[5],
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._connection.close()

    def __enter__(self) -> KiaMemoryStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
