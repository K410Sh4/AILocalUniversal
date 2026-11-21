import httpx
import pytest

from engines.ollama_engine import OllamaEngine, OllamaError, OllamaProtocolError
from model_hub.catalog import CatalogError


@pytest.mark.asyncio
async def test_pull_model_streams_progress_and_requires_success() -> None:
    events = (
        '{"status":"pulling manifest"}\n'
        '{"status":"downloading","digest":"sha256:abc","total":100,"completed":40}\n'
        '{"status":"verifying sha256 digest"}\n'
        '{"status":"success"}\n'
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/pull"
        assert request.read()
        assert request.content == b'{"model":"qwen3.5:2b-q4_K_M","stream":true}'
        return httpx.Response(200, text=events)

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    items = [item async for item in engine.pull_model("qwen3.5:2b-q4_K_M")]

    assert items[1]["completed"] == 40
    assert items[-1]["status"] == "success"


@pytest.mark.asyncio
async def test_pull_model_rejects_stream_without_success_event() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='{"status":"pulling manifest"}\n')

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaProtocolError, match="success"):
        _ = [item async for item in engine.pull_model("qwen3:4b")]


@pytest.mark.asyncio
async def test_pull_model_raises_runtime_error_from_api() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaError, match="model not found"):
        _ = [item async for item in engine.pull_model("missing:latest")]


@pytest.mark.asyncio
async def test_delete_model_uses_explicit_reference() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/api/delete"
        assert request.content == b'{"model":"qwen3:4b"}'
        return httpx.Response(200, json={})

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    await engine.delete_model("qwen3:4b")


@pytest.mark.asyncio
async def test_delete_model_reports_api_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaError, match="model not found"):
        await engine.delete_model("missing:latest")


@pytest.mark.asyncio
async def test_model_management_rejects_non_model_references_before_network() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("No network request should be made for an invalid model ref.")

    engine = OllamaEngine(transport=httpx.MockTransport(handler))
    with pytest.raises(CatalogError):
        _ = [item async for item in engine.pull_model("../../etc/passwd")]
    with pytest.raises(CatalogError):
        await engine.delete_model("https://example.org/model")
