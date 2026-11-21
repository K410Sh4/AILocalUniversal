"""Telemetria Linux de memória PSS para o processo Ollama e seus descendentes.

Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class ProcessMemoryProbeStatus(StrEnum):
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class OllamaProcessMemorySnapshot:
    """Memória proporcional do processo Ollama e da árvore de runners."""

    status: ProcessMemoryProbeStatus
    root_pid: int | None
    process_ids: tuple[int, ...]
    pss_bytes: int | None
    rss_bytes: int | None
    observed_at: str
    reason: str
    root_start_time_ticks: int | None = None


@dataclass(frozen=True, slots=True)
class ProcessMemoryDelta:
    """Variação observada entre duas amostras do mesmo processo Ollama."""

    pss_delta_bytes: int
    rss_delta_bytes: int
    before_at: str
    after_at: str


def _read_cmdline(process_dir: Path) -> list[str] | None:
    try:
        raw = (process_dir / "cmdline").read_bytes()
    except OSError:
        return None
    return [
        part.decode("utf-8", errors="replace")
        for part in raw.split(b"\0")
        if part
    ]


def _is_ollama_server(argv: list[str] | None) -> bool:
    if not argv:
        return False
    executable = Path(argv[0]).name.casefold()
    # O subcomando é o primeiro argumento. Procurar "serve" em qualquer
    # posição confunde "ollama run serve" com o daemon real.
    return executable == "ollama" and len(argv) >= 2 and argv[1].casefold() == "serve"


def _process_stat(process_dir: Path) -> tuple[int, int] | None:
    try:
        stat = (process_dir / "stat").read_text(encoding="utf-8")
    except OSError:
        return None
    closing = stat.rfind(")")
    if closing < 0:
        return None
    fields = stat[closing + 1 :].split()
    if len(fields) <= 19:
        return None
    try:
        parent = int(fields[1])
        start_time = int(fields[19])
    except ValueError:
        return None
    if parent < 0 or start_time < 0:
        return None
    return parent, start_time


def _parse_smaps_rollup(process_dir: Path) -> tuple[int, int] | None:
    try:
        content = (process_dir / "smaps_rollup").read_text(encoding="utf-8")
    except OSError:
        return None

    values: dict[str, int] = {}
    for line in content.splitlines():
        key, separator, value = line.partition(":")
        if not separator or key not in {"Pss", "Rss"}:
            continue
        fields = value.split()
        if len(fields) != 2 or fields[1] != "kB":
            return None
        try:
            amount = int(fields[0])
        except ValueError:
            return None
        if amount < 0:
            return None
        values[key] = amount * 1024

    if "Pss" not in values or "Rss" not in values:
        return None
    return values["Pss"], values["Rss"]


def probe_ollama_process_memory(
    proc_root: str | Path = "/proc",
    *,
    now: datetime | None = None,
) -> OllamaProcessMemorySnapshot:
    """Mede PSS/RSS da árvore local de 'ollama serve' via /proc.

    PSS é a métrica primária: páginas compartilhadas são rateadas entre
    processos. RSS é mantido apenas como referência, pois pode contar páginas
    compartilhadas mais de uma vez. A função não mede VRAM nem processos remotos.
    """
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now precisa conter fuso horário.")
    observed_at = current_time.astimezone(UTC).isoformat()
    root = Path(proc_root)

    try:
        process_dirs = [
            item for item in root.iterdir() if item.name.isdecimal() and item.is_dir()
        ]
    except OSError:
        return OllamaProcessMemorySnapshot(
            ProcessMemoryProbeStatus.NOT_FOUND,
            None,
            (),
            None,
            None,
            observed_at,
            "Diretório proc não está acessível.",
        )

    roots = [
        int(item.name)
        for item in process_dirs
        if _is_ollama_server(_read_cmdline(item))
    ]
    if not roots:
        return OllamaProcessMemorySnapshot(
            ProcessMemoryProbeStatus.NOT_FOUND,
            None,
            (),
            None,
            None,
            observed_at,
            "Nenhum processo local 'ollama serve' foi encontrado.",
        )
    if len(roots) != 1:
        return OllamaProcessMemorySnapshot(
            ProcessMemoryProbeStatus.AMBIGUOUS,
            None,
            tuple(sorted(roots)),
            None,
            None,
            observed_at,
            "Mais de uma instância 'ollama serve' foi encontrada.",
        )

    root_pid = roots[0]
    process_stats = {
        int(item.name): _process_stat(item)
        for item in process_dirs
    }
    root_stat = process_stats.get(root_pid)
    if root_stat is None:
        return OllamaProcessMemorySnapshot(
            ProcessMemoryProbeStatus.INCOMPLETE,
            root_pid,
            (root_pid,),
            None,
            None,
            observed_at,
            "Não foi possível determinar a árvore de processos do Ollama.",
        )

    root_start_time_ticks = root_stat[1]
    parents = {
        pid: stat[0] if stat is not None else None
        for pid, stat in process_stats.items()
    }
    process_ids = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent in parents.items():
            if parent in process_ids and pid not in process_ids:
                process_ids.add(pid)
                changed = True

    pss_total = 0
    rss_total = 0
    for pid in sorted(process_ids):
        process_dir = root / str(pid)
        memory = _parse_smaps_rollup(process_dir)
        current_stat = _process_stat(process_dir)
        if memory is None or current_stat != process_stats.get(pid):
            return OllamaProcessMemorySnapshot(
                ProcessMemoryProbeStatus.INCOMPLETE,
                root_pid,
                tuple(sorted(process_ids)),
                None,
                None,
                observed_at,
                f"PID {pid} mudou durante a leitura ou smaps_rollup está indisponível.",
            )
        pss_total += memory[0]
        rss_total += memory[1]

    return OllamaProcessMemorySnapshot(
        ProcessMemoryProbeStatus.AVAILABLE,
        root_pid,
        tuple(sorted(process_ids)),
        pss_total,
        rss_total,
        observed_at,
        "PSS/RSS medidos para o processo Ollama e todos os descendentes visíveis.",
        root_start_time_ticks=root_start_time_ticks,
    )


def compare_process_memory(
    before: OllamaProcessMemorySnapshot,
    after: OllamaProcessMemorySnapshot,
) -> ProcessMemoryDelta | None:
    """Calcula delta somente quando ambas as amostras são completas e do mesmo PID."""
    if (
        before.status is not ProcessMemoryProbeStatus.AVAILABLE
        or after.status is not ProcessMemoryProbeStatus.AVAILABLE
        or before.root_pid != after.root_pid
        or before.root_start_time_ticks is None
        or before.root_start_time_ticks != after.root_start_time_ticks
        or before.pss_bytes is None
        or after.pss_bytes is None
        or before.rss_bytes is None
        or after.rss_bytes is None
    ):
        return None
    try:
        before_time = datetime.fromisoformat(before.observed_at.replace("Z", "+00:00"))
        after_time = datetime.fromisoformat(after.observed_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if (
        before_time.tzinfo is None
        or after_time.tzinfo is None
        or after_time <= before_time
    ):
        return None
    return ProcessMemoryDelta(
        pss_delta_bytes=after.pss_bytes - before.pss_bytes,
        rss_delta_bytes=after.rss_bytes - before.rss_bytes,
        before_at=before.observed_at,
        after_at=after.observed_at,
    )
