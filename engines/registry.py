"""Registro explícito de adaptadores de inferência."""

from __future__ import annotations

from engines.base import EngineAdapter


class EngineRegistry:
    def __init__(self) -> None:
        self._engines: dict[str, EngineAdapter] = {}

    def register(self, engine: EngineAdapter) -> None:
        name = engine.name.strip()
        if not name:
            raise ValueError("O engine precisa ter nome não vazio.")
        if name in self._engines:
            raise ValueError(f"Engine já registrado: {name}")
        self._engines[name] = engine

    def get(self, name: str) -> EngineAdapter:
        try:
            return self._engines[name]
        except KeyError as exc:
            raise KeyError(f"Engine não registrado: {name}") from exc

    def unregister(self, name: str) -> EngineAdapter:
        try:
            return self._engines.pop(name)
        except KeyError as exc:
            raise KeyError(f"Engine não registrado: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._engines))
