"""Translate AILocal resource budgets into llama-cpp-python constructor options.

The options returned here must be passed when constructing/recreating a
llama_cpp.Llama instance. They are not chat-completion sampling parameters.
"""

from __future__ import annotations

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
