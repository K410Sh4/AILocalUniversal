import pytest

from engines.base import EngineAdapter
from engines.registry import EngineRegistry


class DummyEngine(EngineAdapter):
    name = "dummy"

    async def health(self) -> bool:
        return True

    async def list_models(self):
        return []

    async def stream_chat(self, request):
        if False:
            yield request


def test_registry_registers_and_retrieves_engine() -> None:
    registry = EngineRegistry()
    engine = DummyEngine()
    registry.register(engine)

    assert registry.get("dummy") is engine
    assert registry.names() == ("dummy",)


def test_registry_rejects_duplicate_names() -> None:
    registry = EngineRegistry()
    registry.register(DummyEngine())

    with pytest.raises(ValueError):
        registry.register(DummyEngine())
