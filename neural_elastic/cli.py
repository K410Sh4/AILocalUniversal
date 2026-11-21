"""Command-line interface for the Neural Elastic Execution cache simulator."""

from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
from typing import Sequence

from neural_elastic.contracts import AccessTrace, TraceFormatError
from neural_elastic.simulator import compare_policies
from neural_elastic.synthetic import generate_synthetic_trace


MIB = 1024 * 1024


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compara políticas de cache de especialistas MoE. "
            "O simulador não executa inferência nem mede latência de SSD."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--trace",
        type=Path,
        help="Arquivo JSONL com um registro por acesso a especialista.",
    )
    source.add_argument(
        "--synthetic",
        action="store_true",
        help="Gera um trace sintético reproduzível.",
    )
    parser.add_argument("--capacity-mib", type=float, default=128.0)
    parser.add_argument("--tokens", type=int, default=10_000)
    parser.add_argument("--experts", type=int, default=64)
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--expert-mib", type=float, default=4.0)
    parser.add_argument(
        "--workload",
        choices=("stationary", "phased", "uniform"),
        default="phased",
    )
    parser.add_argument("--phase-tokens", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--statistical-half-life", type=float, default=128.0)
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emite métricas estruturadas em JSON.",
    )
    return parser


def _format_mib(value: int | float) -> str:
    return f"{value / MIB:.2f}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if not isfinite(args.capacity_mib) or args.capacity_mib <= 0:
            raise ValueError("--capacity-mib precisa ser positivo e finito.")
        capacity_bytes = int(args.capacity_mib * MIB)

        if args.trace is not None:
            trace = AccessTrace.from_jsonl(args.trace.read_text(encoding="utf-8"))
            source_label = str(args.trace)
        else:
            if not isfinite(args.expert_mib) or args.expert_mib <= 0:
                raise ValueError("--expert-mib precisa ser positivo e finito.")
            trace = generate_synthetic_trace(
                args.tokens,
                args.experts,
                top_k=args.top_k,
                expert_size_bytes=int(args.expert_mib * MIB),
                workload=args.workload,
                phase_tokens=args.phase_tokens,
                seed=args.seed,
            )
            source_label = (
                f"sintético/{args.workload} (seed={args.seed}, "
                f"tokens={args.tokens}, experts={args.experts}, top_k={args.top_k})"
            )

        results = compare_policies(
            trace,
            capacity_bytes,
            statistical_half_life=args.statistical_half_life,
        )
    except (OSError, TraceFormatError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    if args.json_output:
        payload = {
            "source": source_label,
            "trace": {
                "tokens": trace.token_count,
                "accesses": len(trace.events),
                "unique_experts": len(trace.expert_sizes),
                "uniform_expert_sizes": trace.has_uniform_expert_sizes,
            },
            "capacity_bytes": capacity_bytes,
            "results": [result.to_dict() for result in results],
            "belady_note": (
                "Belady MIN é uma referência offline e só é incluído para "
                "especialistas de tamanho uniforme."
            ),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Neural Elastic Execution — Expert Cache Simulator")
    print(f"Origem: {source_label}")
    print(
        f"Trace: {trace.token_count} tokens, {len(trace.events)} acessos, "
        f"{len(trace.expert_sizes)} especialistas"
    )
    print(f"Capacidade: {_format_mib(capacity_bytes)} MiB")
    print()
    print(
        f"{'Política':<16} {'Hit %':>8} {'Miss %':>8} "
        f"{'Leitura MiB':>13} {'MiB/token':>12} {'Evictions':>11}"
    )
    for result in results:
        print(
            f"{result.policy:<16} {result.hit_rate * 100:>7.2f}% "
            f"{result.miss_rate * 100:>7.2f}% "
            f"{_format_mib(result.bytes_read):>13} "
            f"{_format_mib(result.bytes_read_per_token):>12} "
            f"{result.evictions:>11}"
        )

    if not trace.has_uniform_expert_sizes:
        print(
            "\nBelady MIN omitido: especialistas têm tamanhos diferentes; "
            "farthest-next-use não é garantia de ótimo nesse caso."
        )
    else:
        print(
            "\nBelady MIN é um oráculo offline, não uma política executável "
            "em produção."
        )
    print(
        "Nota: bytes lidos representam misses simulados, não leituras físicas "
        "medidas nem latência de armazenamento."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
