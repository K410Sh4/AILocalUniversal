from concurrent.futures import ThreadPoolExecutor

import pytest

from resources.leases import ModelLeaseConflict, ModelLifecycleLeaseManager


def test_active_use_blocks_model_mutation_until_released() -> None:
    manager = ModelLifecycleLeaseManager()
    use = manager.acquire_use("ollama", "qwen3:4b")

    assert manager.active_use_count("ollama", "qwen3:4b") == 1
    with pytest.raises(ModelLeaseConflict):
        manager.acquire_mutation("ollama", "qwen3:4b")

    use.release()
    mutation = manager.acquire_mutation("ollama", "qwen3:4b")
    assert manager.is_mutating("ollama", "qwen3:4b")
    mutation.release()
    assert not manager.is_mutating("ollama", "qwen3:4b")


def test_multiple_uses_require_all_leases_to_release_before_mutation() -> None:
    manager = ModelLifecycleLeaseManager()
    first = manager.acquire_use("ollama", "qwen3:4b")
    second = manager.acquire_use("OLLAMA", "QWEN3:4B")

    assert manager.active_use_count("ollama", "qwen3:4b") == 2
    first.release()
    assert manager.active_use_count("ollama", "qwen3:4b") == 1
    with pytest.raises(ModelLeaseConflict):
        manager.acquire_mutation("ollama", "qwen3:4b")

    second.release()
    assert manager.active_use_count("ollama", "qwen3:4b") == 0


def test_mutation_blocks_new_uses_and_other_mutations() -> None:
    manager = ModelLifecycleLeaseManager()
    mutation = manager.acquire_mutation("ollama", "qwen3:4b")

    with pytest.raises(ModelLeaseConflict):
        manager.acquire_use("ollama", "qwen3:4b")
    with pytest.raises(ModelLeaseConflict):
        manager.acquire_mutation("ollama", "qwen3:4b")

    mutation.release()
    assert manager.acquire_use("ollama", "qwen3:4b").released is False


def test_release_is_idempotent_and_context_manager_releases() -> None:
    manager = ModelLifecycleLeaseManager()
    lease = manager.acquire_use("ollama", "qwen3:4b")
    lease.release()
    lease.release()
    assert manager.active_use_count("ollama", "qwen3:4b") == 0

    with manager.acquire_mutation("ollama", "qwen3:4b"):
        assert manager.is_mutating("ollama", "qwen3:4b")
    assert not manager.is_mutating("ollama", "qwen3:4b")


def test_lease_manager_is_thread_safe_for_independent_use_leases() -> None:
    manager = ModelLifecycleLeaseManager()

    def use_model(_: int) -> None:
        with manager.acquire_use("ollama", "qwen3:4b"):
            assert manager.active_use_count("ollama", "qwen3:4b") >= 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(use_model, range(32)))

    assert manager.active_use_count("ollama", "qwen3:4b") == 0


@pytest.mark.parametrize(("runtime", "reference"), [("", "qwen3:4b"), ("ollama", "")])
def test_lease_manager_rejects_empty_identity(runtime: str, reference: str) -> None:
    with pytest.raises(ValueError):
        ModelLifecycleLeaseManager().acquire_use(runtime, reference)
