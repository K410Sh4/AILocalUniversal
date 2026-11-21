"""Cliente local JSONL para o processo kia-runtime-host."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HOST_PROTOCOL_VERSION = 1


class KiaRuntimeError(RuntimeError):
    """Falha de protocolo ou erro retornado pelo runtime Rust."""

    def __init__(self, message: str, *, code: str = "runtime_error") -> None:
        super().__init__(message)
        self.code = code


class KiaRuntimeUnavailable(KiaRuntimeError):
    """O executável Rust não pôde ser localizado ou iniciado."""


def _resolve_command(
    command: str | Path | Sequence[str] | None,
) -> list[str]:
    if command is not None:
        resolved = [str(command)] if isinstance(command, (str, Path)) else [
            str(part) for part in command
        ]
        if not resolved or not resolved[0]:
            raise KiaRuntimeUnavailable("Comando do K.IA Runtime Host vazio.")
        return resolved

    configured = os.environ.get("KIA_RUNTIME_HOST")
    if configured:
        return [configured]

    root = Path(__file__).resolve().parents[1]
    candidates = (
        root / "kia" / "target" / "release" / "kia-runtime-host",
        root / "kia" / "target" / "debug" / "kia-runtime-host",
    )
    for candidate in candidates:
        if candidate.is_file():
            return [str(candidate)]

    raise KiaRuntimeUnavailable(
        "Executável kia-runtime-host não encontrado. Compile com "
        "'cd kia && cargo build --release --bin kia-runtime-host' e configure "
        "KIA_RUNTIME_HOST com o caminho do executável."
    )


class KiaRuntimeClient:
    """Mantém um processo Rust e serializa chamadas JSONL request/response.

    O cliente é síncrono e thread-safe: apenas uma solicitação fica em voo por vez.
    O stdout do processo é reservado ao protocolo; stderr permanece ligado ao host.
    """

    def __init__(
        self,
        command: str | Path | Sequence[str] | None = None,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds precisa ser positivo.")
        self.timeout_seconds = float(timeout_seconds)
        self._lock = threading.Lock()
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._sequence = 0
        self._closed = False
        executable = _resolve_command(command)
        try:
            self._process = subprocess.Popen(
                executable,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                encoding="utf-8",
                errors="strict",
                bufsize=1,
                close_fds=True,
            )
        except (OSError, ValueError) as exc:
            raise KiaRuntimeUnavailable(
                f"Não foi possível iniciar kia-runtime-host: {exc}"
            ) from exc

        assert self._process.stdout is not None
        self._reader = threading.Thread(
            target=self._read_stdout,
            args=(self._process.stdout,),
            name="kia-runtime-stdout",
            daemon=True,
        )
        self._reader.start()
        try:
            health = self._request("health")
            if health.get("service") != "kia-cognitive-runtime":
                raise KiaRuntimeError(
                    "O processo respondeu, mas não se identificou como K.IA Runtime Host.",
                    code="invalid_host_identity",
                )
        except Exception:
            self._terminate()
            raise

    def _read_stdout(self, stream: Any) -> None:
        try:
            for line in stream:
                self._responses.put(line)
        finally:
            self._responses.put(None)

    def _request(self, command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._closed:
            raise KiaRuntimeError("K.IA Runtime Client já foi encerrado.", code="client_closed")
        if self._process.poll() is not None:
            raise KiaRuntimeUnavailable(
                f"K.IA Runtime Host encerrou com código {self._process.returncode}.",
                code="host_exited",
            )
        self._sequence += 1
        request_id = f"py-{self._sequence}"
        command_envelope: dict[str, Any] = {"type": command}
        if payload is not None:
            command_envelope["payload"] = payload
        envelope = {
            "protocol_version": HOST_PROTOCOL_VERSION,
            "request_id": request_id,
            "command": command_envelope,
        }

        assert self._process.stdin is not None
        try:
            encoded = json.dumps(
                envelope,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            self._process.stdin.write(encoded + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise KiaRuntimeUnavailable(
                f"Falha ao enviar comando ao K.IA Runtime Host: {exc}",
                code="host_write_failed",
            ) from exc

        try:
            line = self._responses.get(timeout=self.timeout_seconds)
        except queue.Empty as exc:
            raise KiaRuntimeUnavailable(
                f"K.IA Runtime Host excedeu o timeout de {self.timeout_seconds:g}s.",
                code="host_timeout",
            ) from exc
        if line is None:
            raise KiaRuntimeUnavailable(
                f"K.IA Runtime Host fechou o stdout; código {self._process.poll()}.",
                code="host_eof",
            )
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise KiaRuntimeError(
                "O Runtime Host retornou uma linha que não é JSON válido.",
                code="invalid_host_response",
            ) from exc
        if not isinstance(response, dict):
            raise KiaRuntimeError(
                "O Runtime Host retornou um envelope incompatível.",
                code="invalid_host_response",
            )
        if response.get("protocol_version") != HOST_PROTOCOL_VERSION:
            raise KiaRuntimeError(
                "Versão do protocolo retornada pelo host não é compatível.",
                code="protocol_mismatch",
            )
        if response.get("request_id") != request_id:
            raise KiaRuntimeError(
                "request_id da resposta não corresponde à solicitação enviada.",
                code="response_correlation_failed",
            )
        if response.get("ok") is not True:
            error = response.get("error")
            if isinstance(error, dict):
                raise KiaRuntimeError(
                    str(error.get("message", "Falha não especificada pelo host.")),
                    code=str(error.get("code", "host_error")),
                )
            raise KiaRuntimeError("O host rejeitou a solicitação.", code="host_error")
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise KiaRuntimeError(
                "O host retornou um resultado incompatível.",
                code="invalid_host_result",
            )
        return result

    def health(self) -> dict[str, Any]:
        with self._lock:
            return self._request("health")

    def replace_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Substitui a rede, snapshot, budget e lista de executores disponíveis."""
        with self._lock:
            return self._request("replace_state", {"state": state})

    def plan(self, request: dict[str, Any]) -> dict[str, Any]:
        """Solicita um plano Rust; não executa inferência nem ferramentas."""
        with self._lock:
            return self._request("plan", {"request": request})

    def record_feedback(
        self,
        feedback: dict[str, Any],
        *,
        learning_rate: float = 0.1,
    ) -> dict[str, Any]:
        with self._lock:
            return self._request(
                "record_feedback",
                {"feedback": feedback, "learning_rate": learning_rate},
            )

    def inspect(self) -> dict[str, Any]:
        with self._lock:
            return self._request("inspect")

    def _terminate(self) -> None:
        self._closed = True
        process = getattr(self, "_process", None)
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._process.poll() is None:
                with self._lock:
                    self._request("shutdown")
                try:
                    self._process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=2.0)
        finally:
            self._closed = True
            for stream in (self._process.stdin, self._process.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            self._reader.join(timeout=1.0)

    def __enter__(self) -> KiaRuntimeClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
