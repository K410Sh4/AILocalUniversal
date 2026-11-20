import json

from storage.configuration import AppConfig, ConfigurationStore
from storage.conversations import Conversation, ConversationStore


def test_configuration_store_round_trip(tmp_path) -> None:
    path = tmp_path / "config.json"
    store = ConfigurationStore(path)
    config = AppConfig(
        base_url="http://127.0.0.1:11434",
        mode="manual",
        manual_model="qwen2.5:7b",
        preferred_model="llama3.2:3b",
    )

    store.save(config)
    restored = store.load()

    assert restored.to_dict() == config.to_dict()
    assert path.exists()


def test_conversation_store_round_trip(tmp_path) -> None:
    path = tmp_path / "conversations.json"
    store = ConversationStore(path)
    conversation = Conversation(
        title="Conversa de teste",
        messages=[
            {"role": "user", "content": "Olá"},
            {"role": "assistant", "content": "Oi"},
        ],
    )

    store.save_all([conversation])
    restored = store.load_all()

    assert len(restored) == 1
    assert restored[0].id == conversation.id
    assert restored[0].messages == conversation.messages


def test_conversation_store_rejects_invalid_roles(tmp_path) -> None:
    path = tmp_path / "conversations.json"
    path.write_text(
        json.dumps([{"id": "1", "messages": [{"role": "system", "content": "bad"}]}]),
        encoding="utf-8",
    )

    store = ConversationStore(path)

    try:
        store.load_all()
    except ValueError as exc:
        assert "Mensagem inválida" in str(exc)
    else:
        raise AssertionError("Esperava rejeição de mensagem com role não permitido.")
