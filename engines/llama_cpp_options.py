"""Translate AILocal resource budgets into llama-cpp-python constructor options.

The options returned here must be passed when constructing/recreating a
llama_cpp.Llama instance. They are not chat-completion sampling parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.neuralinjector.resources import ResourceBudget


def llama_cpp_constructor_options(
    budget: ResourceBudget,
    *,
    validated_gpu_layers: int | None = None,
) -> dict[str, int]:
    """Map context and CPU threads to llama.cpp's model/context constructor.

    GPU offload is omitted unless a backend-specific probe has already selected
    a layer count. Quantization is determined by the GGUF file itself and cannot
    be changed by these runtime options.
    """
    if budget.context_tokens < 1:
        raise ValueError("budget.context_tokens must be positive")
    if budget.cpu_threads < 1:
        raise ValueError("budget.cpu_threads must be positive")
    if validated_gpu_layers is not None:
        if isinstance(validated_gpu_layers, bool) or not isinstance(validated_gpu_layers, int):
            raise ValueError("validated_gpu_layers must be an integer")
        if validated_gpu_layers < 0:
            raise ValueError("validated_gpu_layers must be non-negative")

    options = {
        "n_ctx": budget.context_tokens,
        "n_threads": budget.cpu_threads,
    }
    if validated_gpu_layers is not None:
        options["n_gpu_layers"] = validated_gpu_layers
    return options


def create_llama_cpp_runtime(
    model_path: str | Path,
    budget: ResourceBudget,
    *,
    validated_gpu_layers: int | None = None,
    llama_class: Any | None = None,
    **model_options: Any,
) -> Any:
    """Create a llama-cpp-python runtime with the resource budget applied.

    `llama_class` is injectable for tests/embedding. When omitted, the optional
    llama-cpp-python package is imported lazily. The selected GGUF is used as-is:
    this function never converts or rewrites model weights.
    """
    path = Path(model_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"GGUF model file not found: {path}")
    if path.suffix.lower() != ".gguf":
        raise ValueError("llama.cpp model path must point to a .gguf file")

    reserved = {"model_path", "n_ctx", "n_threads", "n_gpu_layers"}
    conflicts = reserved.intersection(model_options)
    if conflicts:
        raise ValueError(
            "resource-managed constructor options cannot be overridden: "
            + ", ".join(sorted(conflicts))
        )

    if llama_class is None:
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed; install it before selecting this backend"
            ) from exc
        llama_class = Llama

    constructor_options = dict(model_options)
    constructor_options.update(
        llama_cpp_constructor_options(
            budget,
            validated_gpu_layers=validated_gpu_layers,
        )
    )
    return llama_class(model_path=str(path), **constructor_options)
