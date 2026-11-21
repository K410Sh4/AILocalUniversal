"""Leases de ciclo de vida para impedir mutação de modelos em uso.

Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""

from __future__ import annotations

from threading import Lock, RLock


class ModelLeaseConflict(RuntimeError):
    """Uma mutação ou execução conflita com o ciclo de vida do modelo."""


class ModelLifecycleLease:
    """Lease explícito liberado ao terminar a operação protegida."""

    def __init__(
        self,
        manager: ModelLifecycleLeaseManager,
        key: tuple[str, str],
        mode: str,
    ) -> None:
        self._manager = manager
        self._key = key
        self.mode = mode
        self._release_lock = Lock()
        self._released = False

    @property
    def runtime(self) -> str:
        return self._key[0]

    @property
    def reference(self) -> str:
        return self._key[1]

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        """Libera a lease uma única vez, mesmo com chamadas concorrentes."""
        with self._release_lock:
            if self._released:
                return
            self._manager._release(self._key, self.mode)
            self._released = True

    def __enter__(self) -> ModelLifecycleLease:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()


class ModelLifecycleLeaseManager:
    """Coordena uso e mutação por runtime/referência, sem fingir quota de RAM.

    Leituras/execuções podem coexistir. Pull, remoção ou outra mutação exigem
    exclusividade e são recusados enquanto existir qualquer lease de uso.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._active_uses: dict[tuple[str, str], int] = {}
        self._mutating: set[tuple[str, str]] = set()

    @staticmethod
    def _key(runtime: str, reference: str) -> tuple[str, str]:
        if not isinstance(runtime, str) or not runtime.strip():
            raise ValueError("runtime não pode ficar vazio.")
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("reference não pode ficar vazia.")
        return runtime.strip().casefold(), reference.strip().casefold()

    def acquire_use(self, runtime: str, reference: str) -> ModelLifecycleLease:
        key = self._key(runtime, reference)
        with self._lock:
            if key in self._mutating:
                raise ModelLeaseConflict(
                    f"Modelo {key[1]} está em uma operação de mutação."
                )
            self._active_uses[key] = self._active_uses.get(key, 0) + 1
        return ModelLifecycleLease(self, key, "use")

    def acquire_mutation(self, runtime: str, reference: str) -> ModelLifecycleLease:
        key = self._key(runtime, reference)
        with self._lock:
            if key in self._mutating or self._active_uses.get(key, 0) > 0:
                raise ModelLeaseConflict(
                    f"Modelo {key[1]} está em uso ou já possui uma mutação ativa."
                )
            self._mutating.add(key)
        return ModelLifecycleLease(self, key, "mutation")

    def active_use_count(self, runtime: str, reference: str) -> int:
        key = self._key(runtime, reference)
        with self._lock:
            return self._active_uses.get(key, 0)

    def is_mutating(self, runtime: str, reference: str) -> bool:
        key = self._key(runtime, reference)
        with self._lock:
            return key in self._mutating

    def _release(self, key: tuple[str, str], mode: str) -> None:
        with self._lock:
            if mode == "use":
                count = self._active_uses.get(key, 0)
                if count <= 1:
                    self._active_uses.pop(key, None)
                else:
                    self._active_uses[key] = count - 1
            elif mode == "mutation":
                self._mutating.discard(key)
            else:
                raise ValueError(f"Tipo de lease desconhecido: {mode}")
