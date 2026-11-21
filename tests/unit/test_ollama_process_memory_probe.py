from datetime import UTC, datetime
from pathlib import Path

from resources.telemetry import (
    OllamaProcessMemorySnapshot,
    ProcessMemoryProbeStatus,
    compare_process_memory,
    probe_ollama_process_memory,
)


def _process(
    root: Path,
    pid: int,
    *,
    argv: tuple[str, ...],
    parent: int,
    pss_kb: int = 100,
    rss_kb: int = 200,
) -> None:
    directory = root / str(pid)
    directory.mkdir(parents=True)
    (directory / "cmdline").write_bytes(b"\0".join(item.encode() for item in argv) + b"\0")
    (directory / "stat").write_text(
        f"{pid} (process with spaces) S {parent} 1 1 0 0 0 0",
        encoding="utf-8",
    )
    (directory / "smaps_rollup").write_text(
        f"Pss: {pss_kb} kB\nRss: {rss_kb} kB\n",
        encoding="utf-8",
    )


def test_probe_sums_pss_for_ollama_and_runner_descendants(tmp_path) -> None:
    _process(tmp_path, 100, argv=("ollama", "serve"), parent=1, pss_kb=1000, rss_kb=2000)
    _process(
        tmp_path,
        101,
        argv=("/usr/local/bin/llama-server", "--model", "model.gguf"),
        parent=100,
        pss_kb=3000,
        rss_kb=5000,
    )
    _process(tmp_path, 200, argv=("python", "unrelated.py"), parent=1)

    now = datetime(2030, 1, 1, tzinfo=UTC)
    result = probe_ollama_process_memory(tmp_path, now=now)

    assert result.status is ProcessMemoryProbeStatus.AVAILABLE
    assert result.root_pid == 100
    assert result.process_ids == (100, 101)
    assert result.pss_bytes == 4_000 * 1024
    assert result.rss_bytes == 7_000 * 1024
    assert result.observed_at == now.isoformat()


def test_probe_reports_missing_and_ambiguous_ollama_instances(tmp_path) -> None:
    missing = probe_ollama_process_memory(tmp_path)
    assert missing.status is ProcessMemoryProbeStatus.NOT_FOUND

    _process(tmp_path, 100, argv=("ollama", "serve"), parent=1)
    _process(tmp_path, 200, argv=("ollama", "serve"), parent=1)
    ambiguous = probe_ollama_process_memory(tmp_path)

    assert ambiguous.status is ProcessMemoryProbeStatus.AMBIGUOUS
    assert ambiguous.process_ids == (100, 200)


def test_probe_does_not_return_partial_memory_when_smaps_is_unavailable(tmp_path) -> None:
    _process(tmp_path, 100, argv=("ollama", "serve"), parent=1)
    (tmp_path / "100" / "smaps_rollup").unlink()

    result = probe_ollama_process_memory(tmp_path)

    assert result.status is ProcessMemoryProbeStatus.INCOMPLETE
    assert result.pss_bytes is None
    assert result.rss_bytes is None


def test_compare_memory_requires_same_complete_process_tree() -> None:
    before = OllamaProcessMemorySnapshot(
        ProcessMemoryProbeStatus.AVAILABLE,
        100,
        (100,),
        1_000,
        2_000,
        "2030-01-01T00:00:00+00:00",
        "before",
    )
    after = OllamaProcessMemorySnapshot(
        ProcessMemoryProbeStatus.AVAILABLE,
        100,
        (100, 101),
        5_000,
        7_000,
        "2030-01-01T00:01:00+00:00",
        "after",
    )
    different_root = OllamaProcessMemorySnapshot(
        ProcessMemoryProbeStatus.AVAILABLE,
        200,
        (200,),
        5_000,
        7_000,
        "2030-01-01T00:01:00+00:00",
        "after",
    )

    delta = compare_process_memory(before, after)

    assert delta is not None
    assert delta.pss_delta_bytes == 4_000
    assert delta.rss_delta_bytes == 5_000
    assert compare_process_memory(before, different_root) is None


def test_probe_rejects_naive_timestamp(tmp_path) -> None:
    import pytest

    with pytest.raises(ValueError):
        probe_ollama_process_memory(tmp_path, now=datetime(2030, 1, 1))
