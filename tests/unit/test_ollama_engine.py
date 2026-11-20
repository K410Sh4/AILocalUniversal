import json

import httpx
import pytest

from core.neuralinjector.resources import HardwareSnapshot, ResourceBudget
from engines.base import EngineRequest
from engines.ollama_engine import (
    OllamaEngine,
    OllamaError,
    OllamaProtocolError,
    OllamaResourceProtectionError,
)


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
    budget = ResourceBudget(2048, 0, 1024, 1, "cpu", 3)

    planned = OllamaEngine.apply_resource_budget(request, budget)

    assert planned.options["options"] == {
        "temperature": 0.2,
        "num_ctx": 1024,
        "num_thread": 3,
    }
    assert planned.options["keep_alive"] == "5m"
    assert "num_ctx" not in request.options.get("options", {})


def test_apply_resource_budget_never_increases_existing_context() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
        options={"options": {"num_ctx": 512, "temperature": 0.2}},
    )
    budget = ResourceBudget(2048, 0, 2048, 1, "cpu", 8)

    planned = OllamaEngine.apply_resource_budget(request, budget)

    assert planned.options["options"]["num_ctx"] == 512
    assert planned.options["options"]["num_thread"] == 8


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



def test_apply_resource_budget_never_increases_user_thread_limit() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
        options={"options": {"num_thread": 2}},
    )

    planned = OllamaEngine.apply_resource_budget(
        request,
        ResourceBudget(4096, 0, 2048, 1, "cpu", 8),
    )

    assert planned.options["options"]["num_thread"] == 2


def test_prepare_resource_aware_request_applies_context_and_threads() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
        options={"keep_alive": "5m"},
    )
    hardware = HardwareSnapshot(
        ram_total_mb=8192,
        ram_available_mb=6144,
        cpu_cores=8,
        execution_backends=frozenset({"cpu"}),
    )

    planned, report = OllamaEngine.prepare_resource_aware_request(
        request,
        hardware,
        preferred_profile="balanced",
    )

    assert report.activation_allowed
    assert report.selected_profile == "balanced"
    assert planned.options["options"]["num_ctx"] == 4096
    assert planned.options["options"]["num_thread"] == 8
    assert planned.options["keep_alive"] == "5m"


def test_prepare_resource_aware_request_refuses_below_absolute_floor() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
    )
    hardware = HardwareSnapshot(
        ram_total_mb=1024,
        ram_available_mb=700,
        cpu_cores=2,
        execution_backends=frozenset({"cpu"}),
    )

    with pytest.raises(OllamaResourceProtectionError) as exc_info:
        OllamaEngine.prepare_resource_aware_request(request, hardware)

    assert "1,5 GiB" in str(exc_info.value)
    assert exc_info.value.report.recommendations


@pytest.mark.asyncio
async def test_resource_aware_request_reaches_ollama_with_applied_options() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
    )
    hardware = HardwareSnapshot(
        ram_total_mb=8192,
        ram_available_mb=6144,
        cpu_cores=4,
        execution_backends=frozenset({"cpu"}),
    )
    planned, _report = OllamaEngine.prepare_resource_aware_request(
        request,
        hardware,
        preferred_profile="balanced",
    )

    async def handler(http_request: httpx.Request) -> httpx.Response:
        payload = json.loads(http_request.content)
        assert payload["options"]["num_ctx"] == 4096
        assert payload["options"]["num_thread"] == 4
        return httpx.Response(
            200,
            text=json.dumps({"message": {"content": "OK"}})
            + "\n"
            + json.dumps({"done": True})
            + "\n",
        )

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    events = [event async for event in engine.stream_chat(planned)]

    assert events[-1].done is True


def test_resource_budget_rejects_invalid_cpu_thread_limit() -> None:
    request = EngineRequest(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Olá"}],
    )
    with pytest.raises(ValueError, match="budget.cpu_threads"):
        OllamaEngine.apply_resource_budget(
            request,
            ResourceBudget(1024, 0, 1024, 1, "cpu", 0),
        )



@pytest.mark.asyncio
async def test_stream_chat_forwards_structured_json_format_to_ollama() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["format"] == "json"
        return httpx.Response(
            200,
            text=json.dumps({
                "message": {
                    "role": "assistant",
                    "content": '{"approved":true}',
                }
            })
            + "\\n"
            + json.dumps({"done": True})
            + "\\n",
        )

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    events = [
        event
        async for event in engine.stream_chat(
            EngineRequest(
                model="qwen2.5:7b",
                messages=[{"role": "user", "content": "Review"}],
                options={"format": "json"},
            )
        )
    ]

    assert events[0].content == '{"approved":true}'
    assert events[-1].done is True
