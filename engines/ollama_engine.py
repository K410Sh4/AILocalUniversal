"""Adaptador assíncrono para a API HTTP do Ollama."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from engines.base import EngineAdapter, EngineCapabilities, EngineEvent, EngineRequest, ModelInfo
from model_hub.catalog import validate_model_reference


class OllamaError(RuntimeError):
    """Erro base do adaptador Ollama."""


class OllamaConnectionError(OllamaError):
    """O serviço Ollama não está acessível."""


class OllamaProtocolError(OllamaError):
    """A resposta do servidor não respeita o protocolo esperado."""


class OllamaEngine(EngineAdapter):
    """Cliente sem estado para a API Ollama.

    Um AsyncClient é criado por operação para evitar compartilhar clientes
    assíncronos entre diferentes workers Qt.
    """

    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        *,
        timeout_seconds: float = 180.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(
            timeout_seconds,
            connect=5.0,
            read=timeout_seconds,
        )
        self._transport = transport

    def _client(self, *, timeout: httpx.Timeout | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout or self.timeout,
            transport=self._transport,
            follow_redirects=False,
        )

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
            detail = payload.get("error") or payload.get("message")
        except (ValueError, AttributeError):
            detail = response.text.strip()
        if not detail:
            detail = response.reason_phrase or "erro HTTP"
        return f"Ollama respondeu HTTP {response.status_code}: {detail}"

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def _read_model_capabilities(
        self,
        client: httpx.AsyncClient,
        model_name: str,
        semaphore: asyncio.Semaphore,
    ) -> EngineCapabilities:
        """Lê capacidades declaradas pelo Ollama sem inferi-las pelo nome do modelo."""
        async with semaphore:
            try:
                response = await client.post("/api/show", json={"model": model_name})
                if not response.is_success:
                    return EngineCapabilities(chat=False, verified=False)
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                return EngineCapabilities(chat=False, verified=False)

        raw_capabilities = payload.get("capabilities") if isinstance(payload, dict) else None
        if not isinstance(raw_capabilities, list) or not all(
            isinstance(value, str) for value in raw_capabilities
        ):
            return EngineCapabilities(chat=False, verified=False)

        capabilities = {value.casefold() for value in raw_capabilities}
        supports_completion = "completion" in capabilities
        return EngineCapabilities(
            chat=supports_completion,
            streaming=supports_completion,
            vision="vision" in capabilities,
            tool_calling="tools" in capabilities,
            embeddings="embedding" in capabilities,
            verified=True,
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                if not response.is_success:
                    raise OllamaError(self._error_message(response))
                payload = response.json()

                if not isinstance(payload, dict):
                    raise OllamaProtocolError("Resposta /api/tags deve ser um objeto JSON.")
                raw_models = payload.get("models")
                if not isinstance(raw_models, list):
                    raise OllamaProtocolError("Resposta /api/tags sem uma lista 'models'.")

                semaphore = asyncio.Semaphore(4)

                async def build_model(item: object) -> ModelInfo | None:
                    if not isinstance(item, dict) or not item.get("name"):
                        return None
                    name = str(item["name"])
                    size = item.get("size")
                    capabilities = await self._read_model_capabilities(client, name, semaphore)
                    return ModelInfo(
                        name=name,
                        size_bytes=int(size) if isinstance(size, (int, float)) else None,
                        digest=str(item["digest"]) if item.get("digest") else None,
                        capabilities=capabilities,
                    )

                inspected = await asyncio.gather(*(build_model(item) for item in raw_models))
                return [model for model in inspected if model is not None]
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Não foi possível conectar ao Ollama em {self.base_url}. "
                "Confirme se o serviço está ativo."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaConnectionError("Tempo limite ao consultar o Ollama.") from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(f"Falha HTTP ao consultar Ollama: {exc}") from exc
        except ValueError as exc:
            raise OllamaProtocolError("Ollama retornou JSON inválido em /api/tags.") from exc

    async def pull_model(self, model_name: str) -> AsyncIterator[dict[str, Any]]:
        """Baixa uma referência validada do catálogo e transmite progresso NDJSON.

        O timeout de leitura é ilimitado porque downloads grandes podem durar
        muitos minutos. Cancelar o worker fecha a resposta HTTP; o Ollama
        permite retomar pulls interrompidos numa chamada posterior.
        """
        model_ref = validate_model_reference(model_name)
        completed = False
        timeout = httpx.Timeout(None, connect=5.0)
        try:
            async with self._client(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    "/api/pull",
                    json={"model": model_ref, "stream": True},
                ) as response:
                    if not response.is_success:
                        await response.aread()
                        raise OllamaError(self._error_message(response))

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise OllamaProtocolError(
                                "Ollama enviou um evento NDJSON inválido durante o download."
                            ) from exc
                        if not isinstance(item, dict):
                            raise OllamaProtocolError("Evento de download inválido.")
                        if item.get("error"):
                            raise OllamaError(str(item["error"]))
                        status = item.get("status")
                        if not isinstance(status, str) or not status.strip():
                            raise OllamaProtocolError(
                                "Evento de download sem um campo status válido."
                            )
                        if status.casefold() == "success":
                            completed = True
                        yield item

            if not completed:
                raise OllamaProtocolError(
                    "O download terminou sem confirmação de status success."
                )
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Não foi possível conectar ao Ollama em {self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaConnectionError("Tempo limite ao iniciar o download no Ollama.") from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(f"Falha HTTP durante o download: {exc}") from exc

    async def delete_model(self, model_name: str) -> None:
        """Remove somente o modelo local explicitamente selecionado."""
        model_ref = validate_model_reference(model_name)
        try:
            async with self._client() as client:
                response = await client.request(
                    "DELETE",
                    "/api/delete",
                    json={"model": model_ref},
                )
                if not response.is_success:
                    raise OllamaError(self._error_message(response))
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Não foi possível conectar ao Ollama em {self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaConnectionError("Tempo limite ao remover o modelo no Ollama.") from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(f"Falha HTTP ao remover o modelo: {exc}") from exc

    async def stream_chat(self, request: EngineRequest) -> AsyncIterator[EngineEvent]:
        if not request.model.strip():
            raise ValueError("Um modelo Ollama deve ser selecionado.")
        if not request.messages:
            raise ValueError("A conversa precisa conter ao menos uma mensagem.")

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "stream": True,
        }
        options = request.options.get("options")
        if isinstance(options, dict) and options:
            payload["options"] = options
        if "keep_alive" in request.options:
            payload["keep_alive"] = request.options["keep_alive"]

        completed = False
        try:
            async with self._client() as client:
                async with client.stream("POST", "/api/chat", json=payload) as response:
                    if not response.is_success:
                        await response.aread()
                        raise OllamaError(self._error_message(response))

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise OllamaProtocolError(
                                "Ollama enviou um evento NDJSON inválido."
                            ) from exc

                        if not isinstance(item, dict):
                            raise OllamaProtocolError("Evento de streaming inválido.")
                        if item.get("error"):
                            raise OllamaError(str(item["error"]))

                        message = item.get("message") or {}
                        if not isinstance(message, dict):
                            message = {}
                        content = message.get("content", "")
                        if content:
                            yield EngineEvent(event_type="token", content=str(content))

                        if item.get("done") is True:
                            metadata = {
                                key: item[key]
                                for key in (
                                    "model",
                                    "created_at",
                                    "total_duration",
                                    "load_duration",
                                    "prompt_eval_count",
                                    "prompt_eval_duration",
                                    "eval_count",
                                    "eval_duration",
                                )
                                if key in item
                            }
                            completed = True
                            yield EngineEvent(
                                event_type="done",
                                done=True,
                                metadata=metadata,
                            )
                            break
            if not completed:
                raise OllamaProtocolError(
                    "O stream foi encerrado antes do evento final 'done'."
                )
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Não foi possível conectar ao Ollama em {self.base_url}. "
                "Confirme se o serviço está ativo."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaConnectionError(
                "O Ollama excedeu o tempo limite durante a geração."
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(f"Falha na comunicação com Ollama: {exc}") from exc
