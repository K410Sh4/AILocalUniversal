import pytest

from core.neuralinjector.resources import ResourceBudget
from engines.llama_cpp_options import (
    create_llama_cpp_runtime,
    llama_cpp_constructor_options,
)


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


def test_llama_cpp_runtime_factory_passes_the_budget_to_constructor(tmp_path):
    model_path = tmp_path / "model-q4.gguf"
    model_path.write_bytes(b"GGUF")
    captured = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    budget = ResourceBudget(4096, 0, 4096, 1, "cpu", 8)
    runtime = create_llama_cpp_runtime(
        model_path,
        budget,
        llama_class=FakeLlama,
        use_mmap=True,
    )

    assert isinstance(runtime, FakeLlama)
    assert captured == {
        "model_path": str(model_path.resolve()),
        "use_mmap": True,
        "n_ctx": 4096,
        "n_threads": 8,
    }


def test_llama_cpp_runtime_factory_requires_a_gguf_file(tmp_path):
    wrong_format = tmp_path / "model.bin"
    wrong_format.write_bytes(b"not gguf")

    with pytest.raises(ValueError, match="gguf"):
        create_llama_cpp_runtime(
            wrong_format,
            ResourceBudget(1024, 0, 1024, 1, "cpu", 1),
            llama_class=object,
        )


def test_llama_cpp_runtime_factory_rejects_budget_override(tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"GGUF")

    with pytest.raises(ValueError, match="cannot be overridden"):
        create_llama_cpp_runtime(
            model_path,
            ResourceBudget(1024, 0, 1024, 1, "cpu", 1),
            llama_class=object,
            n_ctx=8192,
        )


def test_llama_cpp_runtime_factory_rejects_missing_model(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_llama_cpp_runtime(
            tmp_path / "missing.gguf",
            ResourceBudget(1024, 0, 1024, 1, "cpu", 1),
            llama_class=object,
        )
