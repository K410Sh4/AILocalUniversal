import pytest

from core.neuralinjector.resources import ResourceBudget
from engines.llama_cpp_options import llama_cpp_constructor_options


def test_llama_cpp_options_map_context_and_threads():
    budget = ResourceBudget(
        ram_limit_mb=4096,
        vram_limit_mb=0,
        context_tokens=4096,
        parallelism=2,
        selected_backend="cpu",
        cpu_threads=8,
    )

    assert llama_cpp_constructor_options(budget) == {
        "n_ctx": 4096,
        "n_threads": 8,
    }


def test_llama_cpp_gpu_layers_require_an_explicit_validated_value():
    budget = ResourceBudget(4096, 0, 2048, 1, "cpu", 4)

    assert llama_cpp_constructor_options(
        budget,
        validated_gpu_layers=12,
    ) == {
        "n_ctx": 2048,
        "n_threads": 4,
        "n_gpu_layers": 12,
    }


@pytest.mark.parametrize("gpu_layers", [-1, True, 1.5])
def test_llama_cpp_rejects_invalid_gpu_layer_count(gpu_layers):
    budget = ResourceBudget(1024, 0, 1024, 1, "cpu", 1)

    with pytest.raises(ValueError):
        llama_cpp_constructor_options(
            budget,
            validated_gpu_layers=gpu_layers,
        )


def test_llama_cpp_rejects_zero_cpu_threads():
    budget = ResourceBudget(1024, 0, 1024, 1, "cpu", 0)

    with pytest.raises(ValueError, match="cpu_threads"):
        llama_cpp_constructor_options(budget)
