"""Adaptador assíncrono para a API HTTP do Ollama."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from core.neuralinjector.resources import (
    CompatibilityReport,
    HardwareSnapshot,
    ProtectionMode,
    ResourceBudget,
    ResourceRequirements,
    build_compatibility_report,
)
from engines.base import EngineAdapter, EngineCapabilities, EngineEvent, EngineRequest, ModelInfo


class OllamaError(RuntimeError):
    """Erro base do adaptador Ollama."""


class OllamaConnectionError(OllamaError):
    """O serviço Ollama não está acessível."""


class OllamaProtocolError(OllamaError):
    """A resposta do servidor não respeita o protocolo esperado."""


class OllamaResourceProtectionError(OllamaError):
    """A política de hardware recusou uma solicitação antes do envio."""

    def __init__(self, report: CompatibilityReport) -> None:
        self.report = report
        super().__init__(
            report.user_message or "Solicitação bloqueada pela política de hardware."
        )


@dataclass(frozen=True)
class OllamaRunningModel:
    """Uso declarado pelo Ollama para um modelo atualmente carregado."""

    name: str
    size_bytes: int | None = None
    vram_bytes: int | None = None
    context_length: int | None = None
    quantization_level: str | None = None


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

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
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

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        parsed = int(value)
        return parsed if parsed >= 0 else None

    @staticmethod
    def apply_resource_budget(
        request: EngineRequest,
        budget: ResourceBudget,
    ) -> EngineRequest:
        """Translate a resource budget into Ollama's per-request runtime options.

        `num_ctx` limits the context window and `num_thread` caps CPU threads.
        Smaller explicit user limits are preserved. This does not select a
        quantized artifact, convert weights, reserve VRAM, unload models, force
        GPU placement, or configure Ollama's server-wide request parallelism.
        """
        if budget.context_tokens < 1:
            raise ValueError("budget.context_tokens must be positive")
        if budget.cpu_threads < 1:
            raise ValueError("budget.cpu_threads must be positive")

        options = dict(request.options)
        raw_model_options = options.get("options", {})
        if raw_model_options is None:
            model_options: dict[str, Any] = {}
        elif isinstance(raw_model_options, dict):
            model_options = dict(raw_model_options)
        else:
            raise ValueError("request.options['options'] must be an object")

        existing_context = model_options.get("num_ctx")
        if existing_context is not None:
            if isinstance(existing_context, bool) or not isinstance(existing_context, int):
                raise ValueError("num_ctx must be an integer")
            if existing_context < 1:
                raise ValueError("num_ctx must be positive")
            context_limit = min(existing_context, budget.context_tokens)
        else:
            context_limit = budget.context_tokens

        existing_threads = model_options.get("num_thread")
        if existing_threads is not None:
            if isinstance(existing_threads, bool) or not isinstance(existing_threads, int):
                raise ValueError("num_thread must be an integer")
            if existing_threads < 1:
                raise ValueError("num_thread must be positive")
            thread_limit = min(existing_threads, budget.cpu_threads)
        else:
            thread_limit = budget.cpu_threads

        model_options["num_ctx"] = context_limit
        model_options["num_thread"] = thread_limit
        options["options"] = model_options
        return EngineRequest(
            model=request.model,
            messages=request.messages,
            options=options,
        )

    @staticmethod
    def prepare_resource_aware_request(
        request: EngineRequest,
        hardware: HardwareSnapshot,
        *,
        preferred_profile: str | None = None,
        protection_mode: ProtectionMode | str = ProtectionMode.PROTECTED,
        requirements: ResourceRequirements = ResourceRequirements(),
    ) -> tuple[EngineRequest, CompatibilityReport]:
        """Plan a request and apply the Ollama-supported subset of its budget.

        The request is rejected before network I/O when activation is not allowed.
        Quantization remains an artifact-level choice; server placement and global
        parallelism remain controlled by Ollama itself.
        """
        report = build_compatibility_report(
            hardware,
            requirements,
            preferred_profile,
            protection_mode=protection_mode,
        )
        if not report.activation_allowed or report.budget is None:
            raise OllamaResourceProtectionError(report)
        planned_request = OllamaEngine.apply_resource_budget(request, report.budget)
        return planned_request, report

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[ModelInfo]:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                if not response.is_success:
                    raise OllamaError(self._error_message(response))
                payload = response.json()
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

        if not isinstance(payload, dict):
            raise OllamaProtocolError("Resposta /api/tags deve ser um objeto JSON.")
        raw_models = payload.get("models")
        if not isinstance(raw_models, list):
            raise OllamaProtocolError("Resposta /api/tags sem uma lista 'models'.")

        models: list[ModelInfo] = []
        for item in raw_models:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            size = item.get("size")
            models.append(
                ModelInfo(
                    name=str(item["name"]),
                    size_bytes=int(size) if isinstance(size, (int, float)) else None,
                    digest=str(item["digest"]) if item.get("digest") else None,
                    capabilities=EngineCapabilities(chat=True, streaming=True),
                )
            )
        return models

    async def list_running_models(self) -> list[OllamaRunningModel]:
        """Read current Ollama allocations through GET /api/ps."""
        try:
            async with self._client() as client:
                response = await client.get("/api/ps")
                if not response.is_success:
                    raise OllamaError(self._error_message(response))
                payload = response.json()
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Não foi possível conectar ao Ollama em {self.base_url}. "
                "Confirme se o serviço está ativo."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaConnectionError("Tempo limite ao consultar modelos carregados.") from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(
                f"Falha HTTP ao consultar modelos carregados: {exc}"
            ) from exc
        except ValueError as exc:
            raise OllamaProtocolError("Ollama retornou JSON inválido em /api/ps.") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            raise OllamaProtocolError("Resposta /api/ps deve conter a lista 'models'.")

        running: list[OllamaRunningModel] = []
        for item in payload["models"]:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            details = item.get("details")
            if not isinstance(details, dict):
                details = {}
            running.append(
                OllamaRunningModel(
                    name=str(item["name"]),
                    size_bytes=self._optional_int(item.get("size")),
                    vram_bytes=self._optional_int(item.get("size_vram")),
                    context_length=self._optional_int(item.get("context_length")),
                    quantization_level=(
                        str(details["quantization_level"])
                        if details.get("quantization_level")
                        else None
                    ),
                )
            )
        return running

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
