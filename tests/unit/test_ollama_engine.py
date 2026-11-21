import json

import httpx
import pytest

from engines.base import EngineRequest
from engines.ollama_engine import OllamaEngine, OllamaError, OllamaProtocolError


@pytest.mark.asyncio
async def test_health_and_model_inventory() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "qwen2.5:7b", "size": 1234, "digest": "abc"},
                        {"name": "llama3.2:3b", "size": 5678},
                        {"name": "qwen3-embedding:0.6b", "size": 9012},
                    ]
                },
            )
        assert request.url.path == "/api/show"
        model_name = json.loads(request.content)["model"]
        capabilities = {
            "qwen2.5:7b": ["completion"],
            "llama3.2:3b": ["completion", "tools", "vision"],
            "qwen3-embedding:0.6b": ["embedding"],
        }[model_name]
        return httpx.Response(200, json={"capabilities": capabilities})

    engine = OllamaEngine(transport=httpx.MockTransport(handler))

    assert await engine.health()
    models = await engine.list_models()

    assert [model.name for model in models] == [
        "qwen2.5:7b",
        "llama3.2:3b",
        "qwen3-embedding:0.6b",
    ]
    assert models[0].size_bytes == 1234
    assert models[0].digest == "abc"
    assert models[0].capabilities.chat is True
    assert models[0].capabilities.streaming is True
    assert models[1].capabilities.tool_calling is True
    assert models[1].capabilities.vision is True
    assert models[2].capabilities.chat is False
    assert models[2].capabilities.embeddings is True
    assert models[2].capabilities.verified is True


@pytest.mark.asyncio
async def test_stream_chat_normalizes_tokens_and_metadata() -> None:
    body = (
        json.dumps({"message": {"role": "assistant", "content": "Olá"}})
        + "\n"
        + json.dumps({"message": {"role": "assistant", "content": " mundo"}})
        + "\n"
        + json.dumps({"done": True, "eval_count": 2, "eval_duration": 1000000000})
        + "\n"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "qwen2.5:7b"
        assert payload["stream"] is True
        assert payload["keep_alive"] == "5m"
        assert payload["options"] == {"num_thread": 8}
        assert payload["messages"][0]["role"] == "user"
        return httpx.Response(200, text=body)

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    events = [
        event
        async for event in engine.stream_chat(
            EngineRequest(
                model="qwen2.5:7b",
                messages=[{"role": "user", "content": "Oi"}],
                options={"keep_alive": "5m", "options": {"num_thread": 8}},
            )
        )
    ]

    assert [event.content for event in events if event.event_type == "token"] == [
        "Olá",
        " mundo",
    ]
    assert events[-1].done is True
    assert events[-1].metadata["eval_count"] == 2


@pytest.mark.asyncio
async def test_stream_chat_reports_server_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    engine = OllamaEngine(transport=httpx.MockTransport(handler))

    with pytest.raises(OllamaError, match="model not found"):
        _ = [
            event
            async for event in engine.stream_chat(
                EngineRequest(model="missing", messages=[{"role": "user", "content": "Oi"}])
            )
        ]


@pytest.mark.asyncio
async def test_stream_chat_rejects_stream_without_done_event() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=json.dumps({"message": {"content": "parcial"}}) + "\n",
        )

    engine = OllamaEngine(transport=httpx.MockTransport(handler))

    with pytest.raises(OllamaProtocolError, match="evento final"):
        _ = [
            event
            async for event in engine.stream_chat(
                EngineRequest(model="test", messages=[{"role": "user", "content": "Oi"}])
            )
        ]


@pytest.mark.asyncio
async def test_model_without_capability_metadata_is_not_assumed_to_support_chat() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "legacy-model"}]})
        assert request.url.path == "/api/show"
        return httpx.Response(200, json={"details": {"family": "unknown"}})

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    models = await engine.list_models()

    assert len(models) == 1
    assert models[0].capabilities.chat is False
    assert models[0].capabilities.verified is False
