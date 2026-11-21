import httpx
import pytest

from engines.ollama_engine import OllamaEngine


@pytest.mark.asyncio
async def test_ollama_show_exposes_qwen3_memory_metadata() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "qwen3:4b", "size": 2_600_000_000, "digest": "abc"}
                    ]
                },
            )
        assert request.url.path == "/api/show"
        return httpx.Response(
            200,
            json={
                "capabilities": ["completion", "tools"],
                "details": {"quantization_level": "Q4_K_M", "family": "qwen3"},
                "model_info": {
                    "general.architecture": "qwen3",
                    "general.parameter_count": 4_000_000_000,
                    "qwen3.context_length": 32_768,
                    "qwen3.block_count": 36,
                    "qwen3.attention.head_count_kv": 8,
                    "qwen3.attention.key_length": 128,
                    "qwen3.attention.value_length": 128,
                },
            },
        )

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    models = await engine.list_models()

    assert len(models) == 1
    model = models[0]
    assert model.parameter_count == 4_000_000_000
    assert model.architecture == "qwen3"
    assert model.quantization == "Q4_K_M"
    assert model.context_window == 32_768
    assert model.kv_cache_bytes_per_token == 147_456
    assert model.capabilities.chat is True
    assert model.capabilities.tool_calling is True


@pytest.mark.asyncio
async def test_ollama_does_not_guess_kv_cache_for_hybrid_architecture() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "hybrid:test", "size": 1}]})
        return httpx.Response(
            200,
            json={
                "capabilities": ["completion"],
                "details": {"quantization_level": "Q4_K_M"},
                "model_info": {
                    "general.architecture": "qwen3_5",
                    "general.parameter_count": 2_000_000_000,
                    "qwen3_5.context_length": 32_768,
                    "qwen3_5.block_count": 24,
                    "qwen3_5.attention.head_count_kv": 4,
                    "qwen3_5.attention.key_length": 128,
                    "qwen3_5.attention.value_length": 128,
                },
            },
        )

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    model = (await engine.list_models())[0]

    assert model.parameter_count == 2_000_000_000
    assert model.quantization == "Q4_K_M"
    assert model.kv_cache_bytes_per_token is None
