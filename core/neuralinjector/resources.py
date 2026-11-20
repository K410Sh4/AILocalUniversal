"""Backend-agnostic hardware-aware planning for NeuralInjector."""
from __future__ import annotations
import os
import platform
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping

class BenchmarkMode(str, Enum):
    NONE = "none"
    QUICK = "quick"
    FULL = "full"

@dataclass(frozen=True)
class HardwareSnapshot:
    ram_total_mb: int
    ram_available_mb: int
    vram_total_mb: int | None = None
    vram_available_mb: int | None = None
    cpu_cores: int = 1
    backend_features: frozenset[str] = frozenset()
    execution_backends: frozenset[str] = frozenset({"cpu"})
    platform_id: str = field(default_factory=platform.system)
    def __post_init__(self):
        if self.ram_total_mb <= 0 or not 0 <= self.ram_available_mb <= self.ram_total_mb:
            raise ValueError("invalid RAM measurements")
        if self.cpu_cores < 1:
            raise ValueError("cpu_cores must be positive")

@dataclass(frozen=True)
class ResourceRequirements:
    min_ram_mb: int = 0
    min_vram_mb: int = 0
    min_disk_mb: int = 0
    min_context_tokens: int = 512
    supported_execution: tuple[str, ...] = ("cpu", "gpu")
    required_features: tuple[str, ...] = ()
    def __post_init__(self):
        if min(self.min_ram_mb, self.min_vram_mb, self.min_disk_mb) < 0 or self.min_context_tokens < 1:
            raise ValueError("invalid resource requirements")

@dataclass(frozen=True)
class ResourceBudget:
    ram_limit_mb: int
    vram_limit_mb: int
    context_tokens: int
    parallelism: int

@dataclass(frozen=True)
class HardwareProfile:
    profile_id: str
    min_ram_mb: int
    max_ram_fraction: float
    context_tokens: int
    parallelism: int
    preferred_backends: tuple[str, ...] = ("gpu", "cpu")
    min_vram_mb: int = 0
    def __post_init__(self):
        if not 0 < self.max_ram_fraction <= 1 or self.context_tokens < 1 or self.parallelism < 1:
            raise ValueError("invalid profile limits")

@dataclass(frozen=True)
class CompatibilityReport:
    compatible: bool
    selected_profile: str | None
    budget: ResourceBudget | None
    reasons: tuple[str, ...] = ()
    fallbacks: tuple[str, ...] = ()
    benchmark_mode: str = BenchmarkMode.NONE.value
    benchmark_result: Mapping[str, float] | None = None

CANONICAL_PROFILES = (
    HardwareProfile("minimal", 2048, .55, 2048, 1, ("cpu", "gpu")),
    HardwareProfile("balanced", 4096, .65, 4096, 1),
    HardwareProfile("performance", 8192, .75, 8192, 2),
    HardwareProfile("max_quality", 16384, .80, 16384, 4),
)

def detect_hardware() -> HardwareSnapshot:
    """Detect RAM/CPU with stdlib; GPU/VRAM remain unknown until a backend reports them."""
    total = max(1, int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1048576))
    available = total
    try:
        with open("/proc/meminfo", encoding="ascii") as stream:
            for line in stream:
                if line.startswith("MemAvailable:"):
                    available = int(line.split()[1]) // 1024
                    break
    except (OSError, ValueError, IndexError):
        pass
    return HardwareSnapshot(total, min(total, max(0, available)),
        cpu_cores=os.cpu_count() or 1, execution_backends=frozenset({"cpu"}),
        platform_id=platform.system().lower())

def _reasons(profile: HardwareProfile, hw: HardwareSnapshot) -> list[str]:
    out = []
    if hw.ram_total_mb < profile.min_ram_mb or hw.ram_available_mb < profile.min_ram_mb:
        out.append(f"{profile.profile_id}: RAM abaixo do mínimo de {profile.min_ram_mb} MiB")
    if profile.min_vram_mb and (hw.vram_available_mb is None or hw.vram_available_mb < profile.min_vram_mb):
        out.append(f"{profile.profile_id}: VRAM ausente ou insuficiente")
    if not set(profile.preferred_backends).intersection(hw.execution_backends):
        out.append(f"{profile.profile_id}: backend incompatível")
    return out

def select_profile(hw: HardwareSnapshot, preferred: str | None = None) -> HardwareProfile:
    profiles = {p.profile_id: p for p in CANONICAL_PROFILES}
    if preferred is not None and preferred not in profiles:
        raise ValueError(f"unknown hardware profile: {preferred}")
    eligible = [p for p in CANONICAL_PROFILES if not _reasons(p, hw)]
    if preferred and any(p.profile_id == preferred for p in eligible):
        return profiles[preferred]
    return eligible[-1] if eligible else profiles["minimal"]

def build_compatibility_report(hw: HardwareSnapshot,
    requirements: ResourceRequirements = ResourceRequirements(),
    preferred_profile: str | None = None,
    benchmark_mode: BenchmarkMode | str = BenchmarkMode.NONE,
    benchmark: Callable[[str], Mapping[str, float]] | None = None) -> CompatibilityReport:
    """Plan resource use; benchmark callbacks run only after explicit opt-in."""
    mode = BenchmarkMode(benchmark_mode)
    reasons = []
    if hw.ram_total_mb < requirements.min_ram_mb or hw.ram_available_mb < requirements.min_ram_mb:
        reasons.append("RAM abaixo do requisito mínimo do pacote")
    if requirements.min_vram_mb and (hw.vram_available_mb is None or hw.vram_available_mb < requirements.min_vram_mb):
        reasons.append("VRAM necessária, mas ausente ou insuficiente")
    missing = set(requirements.required_features) - set(hw.backend_features)
    if missing:
        reasons.append("Recursos de backend ausentes: " + ", ".join(sorted(missing)))
    if not set(requirements.supported_execution).intersection(hw.execution_backends):
        reasons.append("Nenhum backend aceito está disponível")
    profile = select_profile(hw, preferred_profile)
    profile_failures = _reasons(profile, hw)
    if profile_failures:
        reasons.extend(profile_failures)
    budget = ResourceBudget(int(hw.ram_available_mb * profile.max_ram_fraction),
        hw.vram_available_mb or 0, max(requirements.min_context_tokens, profile.context_tokens),
        min(profile.parallelism, max(1, hw.cpu_cores)))
    fallbacks = []
    if hw.vram_available_mb is None or hw.vram_available_mb == 0:
        fallbacks.append("não presumir GPU; preferir CPU quando suportado")
    if profile.profile_id == "minimal":
        fallbacks.append("desativar componentes opcionais e limitar concorrência a uma tarefa")
    if budget.ram_limit_mb < requirements.min_ram_mb:
        fallbacks.append("buscar artefato alternativo validado; não violar requisito mínimo")
    result = None
    if mode is not BenchmarkMode.NONE:
        if benchmark is None:
            fallbacks.append("benchmark solicitado sem executor; seleção permanece heurística")
        else:
            result = dict(benchmark(mode.value))
    return CompatibilityReport(not reasons, profile.profile_id, budget,
        tuple(dict.fromkeys(reasons)), tuple(fallbacks), mode.value, result)
