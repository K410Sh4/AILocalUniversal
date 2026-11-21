"""Armazenamento JSON local de conversas."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def default_conversations_path() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "ailocal-universal" / "conversations.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Conversation:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "Nova conversa"
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Conversation:
        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            raise ValueError("Histórico de mensagens inválido.")
        for message in messages:
            if (
                not isinstance(message, dict)
                or message.get("role") not in {"user", "assistant"}
                or not isinstance(message.get("content"), str)
            ):
                raise ValueError("Mensagem inválida no histórico.")
        return cls(
            id=str(payload["id"]),
            title=str(payload.get("title") or "Nova conversa"),
            messages=messages,
            created_at=str(payload.get("created_at") or _now()),
            updated_at=str(payload.get("updated_at") or _now()),
        )


class ConversationStore:
    """Persiste conversas com escrita atômica e permissões privadas."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_conversations_path()

    def load_all(self) -> list[Conversation]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("O arquivo de conversas precisa conter uma lista.")
            return [Conversation.from_dict(item) for item in payload]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Não foi possível carregar o histórico: {exc}") from exc

    def save_all(self, conversations: list[Conversation]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(
                    [conversation.to_dict() for conversation in conversations],
                    stream,
                    ensure_ascii=False,
                    indent=2,
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def delete(
        self,
        conversation_id: str,
        *,
        conversations: list[Conversation] | None = None,
    ) -> bool:
        """Remove uma conversa pelo ID e persiste atomicamente as restantes."""
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError("O identificador da conversa precisa ser texto não vazio.")
        source = list(conversations) if conversations is not None else self.load_all()
        retained = [item for item in source if item.id != conversation_id]
        if len(retained) == len(source):
            return False
        self.save_all(retained)
        return True

    def save(self, conversation: Conversation) -> None:
        conversation.updated_at = _now()
        conversations = self.load_all()
        for index, existing in enumerate(conversations):
            if existing.id == conversation.id:
                conversations[index] = conversation
                break
        else:
            conversations.append(conversation)
        self.save_all(conversations)
