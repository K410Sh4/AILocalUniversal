import json

import httpx
import pytest

from core.neuralinjector.resources import ResourceBudget
from engines.base import EngineRequest
from engines.ollama_engine import OllamaEngine, OllamaError, OllamaProtocolError


@pytest.mark.asyncio
async def test_health_and_model_inventory() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen2.5:7b", "size": 1234, "digest": "abc"},
                    {"name": "llama3.2:3b", "size": 5678},
                ]
            },
        )

    engine = OllamaEngine(transport=httpx.MockTransport(handler))

    assert await engine.health()
    models = await engine.list_models()

    assert [model.name for model in models] == ["qwen2.5:7b", "llama3.2:3b"]
    assert models[0].size_bytes == 1234
    assert models[0].digest == "abc"
    assert models[0].capabilities.streaming is True


@pytest.mark.asyncio
async def test_list_running_models_reports_memory_context_and_quantization() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/ps"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "qwen3:4b",
                        "size": 3_000_000_000,
                        "size_vram": 2_000_000_000,
                        "context_length": 4096,
                        "details": {"quantization_level": "Q4_K_M"},
                    },
                    {"name": "cpu-model", "size": 900_000_000, "size_vram": 0},
                ]
            },
        )

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    running = await engine.list_running_models()

    assert len(running) == 2
    assert running[0].name == "qwen3:4b"
    assert running[0].size_bytes == 3_000_000_000
    assert running[0].vram_bytes == 2_000_000_000
    assert running[0].context_length == 4096
    assert running[0].quantization_level == "Q4_K_M"
    assert running[1].vram_bytes == 0
    assert running[1].context_length is None


@pytest.mark.asyncio
async def test_list_running_models_rejects_malformed_payload() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": "invalid"})

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaProtocolError, match="lista 'models'"):
        await engine.list_running_models()


def test_apply_resource_budget_sets_context_and_preserves_other_options() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
        options={"options": {"temperature": 0.2}, "keep_alive": "5m"},
    )
    budget = ResourceBudget(2048, 0, 1024, 1, "cpu")

    planned = OllamaEngine.apply_resource_budget(request, budget)

    assert planned.options["options"] == {"temperature": 0.2, "num_ctx": 1024}
    assert planned.options["keep_alive"] == "5m"
    assert "num_ctx" not in request.options.get("options", {})


def test_apply_resource_budget_never_increases_existing_context() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
        options={"options": {"num_ctx": 512, "temperature": 0.2}},
    )
    budget = ResourceBudget(2048, 0, 2048, 1, "cpu")

    planned = OllamaEngine.apply_resource_budget(request, budget)

    assert planned.options["options"]["num_ctx"] == 512


def test_apply_resource_budget_rejects_invalid_context_values() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
        options={"options": {"num_ctx": 0}},
    )
    with pytest.raises(ValueError, match="num_ctx must be positive"):
        OllamaEngine.apply_resource_budget(
            request,
            ResourceBudget(1024, 0, 1024, 1, "cpu"),
        )


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
        assert payload["messages"][0]["role"] == "user"
        return httpx.Response(200, text=body)

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    events = [
        event
        async for event in engine.stream_chat(
            EngineRequest(
                model="qwen2.5:7b",
                messages=[{"role": "user", "content": "Oi"}],
                options={"keep_alive": "5m"},
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
