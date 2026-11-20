"""Backend-agnostic hardware planning and adaptive resource policies."""

from __future__ import annotations

import csv
import glob
import io
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path


class BenchmarkMode(str, Enum):
    NONE = "none"
    QUICK = "quick"
    FULL = "full"


class ProtectionMode(str, Enum):
    PERMISSIVE = "permissive"
    ADAPTIVE = "adaptive"
    PROTECTED = "protected"


class ResourcePressure(str, Enum):
    NORMAL = "normal"
    CONSTRAINED = "constrained"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass(frozen=True)
class GPUDevice:
    """GPU visible to the OS; this does not imply an inference backend is usable."""

    name: str
    vendor: str
    total_memory_mb: int | None = None
    available_memory_mb: int | None = None
    memory_kind: str = "unknown"
    detection_source: str = "unknown"


@dataclass(frozen=True)
class QuantizationPolicy:
    """Ordered candidates only; selecting one never converts model weights."""

    preferred: tuple[str, ...] = ("Q5_K_M", "Q4_K_M", "Q4_0")
    low_memory_preferred: tuple[str, ...] = ("Q4_K_M", "Q4_0", "Q3_K_M", "Q2_K")
    low_memory_threshold_mb: int = 8192
    allow_lower_precision_fallback: bool = True

    def __post_init__(self) -> None:
        if self.low_memory_threshold_mb < 0:
            raise ValueError("low_memory_threshold_mb cannot be negative")
        if not self.preferred or not self.low_memory_preferred:
            raise ValueError("quantization candidate lists cannot be empty")

    def candidates_for(self, available_ram_mb: int) -> tuple[str, ...]:
        low_memory = available_ram_mb < self.low_memory_threshold_mb
        primary = self.low_memory_preferred if low_memory else self.preferred
        if not self.allow_lower_precision_fallback:
            return tuple(dict.fromkeys(primary))
        fallback = self.preferred if low_memory else self.low_memory_preferred
        return tuple(dict.fromkeys((*primary, *fallback)))


@dataclass(frozen=True)
class HardwareSnapshot:
    ram_total_mb: int
    ram_available_mb: int
    vram_total_mb: int | None = None
    vram_available_mb: int | None = None
    cpu_cores: int = 1
    backend_features: frozenset[str] = frozenset()
    execution_backends: frozenset[str] = frozenset({"cpu"})
    platform_id: str = field(default_factory=lambda: platform.system().lower())
    disk_free_mb: int | None = None
    gpu_devices: tuple[GPUDevice, ...] = ()

    def __post_init__(self) -> None:
        if self.ram_total_mb <= 0 or not 0 <= self.ram_available_mb <= self.ram_total_mb:
            raise ValueError("invalid RAM measurements")
        if self.cpu_cores < 1:
            raise ValueError("cpu_cores must be positive")
        if not self.execution_backends:
            raise ValueError("execution_backends cannot be empty")
        if self.vram_total_mb is not None and self.vram_total_mb < 0:
            raise ValueError("vram_total_mb cannot be negative")
        if self.vram_available_mb is not None:
            if self.vram_available_mb < 0:
                raise ValueError("vram_available_mb cannot be negative")
            if self.vram_total_mb is not None and self.vram_available_mb > self.vram_total_mb:
                raise ValueError("available VRAM cannot exceed total VRAM")
        if self.disk_free_mb is not None and self.disk_free_mb < 0:
            raise ValueError("disk_free_mb cannot be negative")


@dataclass(frozen=True)
class ResourceRequirements:
    min_ram_mb: int = 0
    min_vram_mb: int = 0
    min_disk_mb: int = 0
    min_context_tokens: int = 512
    supported_execution: tuple[str, ...] = ("cpu", "gpu")
    required_features: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if min(self.min_ram_mb, self.min_vram_mb, self.min_disk_mb) < 0:
            raise ValueError("resource requirements cannot be negative")
        if self.min_context_tokens < 1:
            raise ValueError("min_context_tokens must be positive")
        if not self.supported_execution:
            raise ValueError("supported_execution cannot be empty")


@dataclass(frozen=True)
class ResourceBudget:
    ram_limit_mb: int
    vram_limit_mb: int
    context_tokens: int
    parallelism: int
    selected_backend: str = "cpu"
    cpu_threads: int = 1


@dataclass(frozen=True)
class HardwareProfile:
    profile_id: str
    min_ram_mb: int
    max_ram_fraction: float
    context_tokens: int
    parallelism: int
    preferred_backends: tuple[str, ...] = ("gpu", "cpu")
    min_vram_mb: int = 0
    quantization_policy: QuantizationPolicy = field(default_factory=QuantizationPolicy)
    description: str = ""
    min_context_tokens: int = 512
    priorities: tuple[str, ...] = ("quality", "latency", "memory")
    max_cpu_threads: int = 8
    allow_cpu_fallback: bool = True
    require_gpu: bool = False
    disable_optional_components: bool = True
    reduce_context: bool = True
    reduce_parallelism: bool = True
    allow_artifact_fallback: bool = True
    benchmark_allowed: tuple[str, ...] = ("none", "quick", "full")

    def __post_init__(self) -> None:
        if self.min_ram_mb < 0 or self.min_vram_mb < 0:
            raise ValueError("profile requirements cannot be negative")
        if not 0 < self.max_ram_fraction <= 1:
            raise ValueError("max_ram_fraction must be in (0, 1]")
        if self.context_tokens < 1 or self.min_context_tokens < 1:
            raise ValueError("context limits must be positive")
        if self.min_context_tokens > self.context_tokens:
            raise ValueError("minimum context cannot exceed target context")
        if self.parallelism < 1 or self.max_cpu_threads < 1:
            raise ValueError("parallelism and CPU threads must be positive")
        if not self.preferred_backends or not self.priorities or not self.benchmark_allowed:
            raise ValueError("profile lists cannot be empty")

    def to_dict(self) -> dict[str, object]:
        """Serialize the canonical Python profile into the public JSON contract."""
        return {
            "profile_id": self.profile_id,
            "profile_version": "1.0.0",
            "description": self.description,
            "requirements": {
                "min_ram_mb": self.min_ram_mb,
                "min_vram_mb": self.min_vram_mb,
                "min_disk_mb": 0,
                "min_context_tokens": self.min_context_tokens,
            },
            "objectives": {
                "priority": list(self.priorities),
                "interactive": True,
            },
            "budget": {
                "max_ram_fraction": self.max_ram_fraction,
                "target_context_tokens": self.context_tokens,
                "max_parallelism": self.parallelism,
                "max_cpu_threads": self.max_cpu_threads,
            },
            "execution": {
                "preferred_backends": list(self.preferred_backends),
                "allow_cpu_fallback": self.allow_cpu_fallback,
                "require_gpu": self.require_gpu,
            },
            "degradation": {
                "disable_optional_components": self.disable_optional_components,
                "reduce_context": self.reduce_context,
                "reduce_parallelism": self.reduce_parallelism,
                "allow_artifact_fallback": self.allow_artifact_fallback,
            },
            "benchmark": {
                "default": "none",
                "allowed": list(self.benchmark_allowed),
            },
            "quantization_policy": {
                "preferred": list(self.quantization_policy.preferred),
                "low_memory_preferred": list(self.quantization_policy.low_memory_preferred),
                "low_memory_threshold_mb": self.quantization_policy.low_memory_threshold_mb,
                "allow_lower_precision_fallback": self.quantization_policy.allow_lower_precision_fallback,
            },
        }


@dataclass(frozen=True)
class CompatibilityReport:
    compatible: bool
    selected_profile: str | None
    budget: ResourceBudget | None
    reasons: tuple[str, ...] = ()
    fallbacks: tuple[str, ...] = ()
    benchmark_mode: str = BenchmarkMode.NONE.value
    benchmark_result: Mapping[str, float] | None = None
    activation_allowed: bool = False
    protection_mode: str = ProtectionMode.ADAPTIVE.value
    eligible_profiles: tuple[str, ...] = ()
    quantization_candidate: str | None = None
    user_message: str = ""
    recommendations: tuple[str, ...] = ()


@dataclass(frozen=True)
class DynamicResourceDecision:
    pressure: ResourcePressure
    available_fraction: float
    pause_new_loads: bool
    reject_new_loads: bool
    suspend_optional_work: bool
    parallelism_limit: int | None
    recommended_context_tokens: int | None
    actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RamMeasurement:
    total_mb: int
    available_mb: int


def _read_int(path: str | Path) -> int | None:
    try:
        value = Path(path).read_text(encoding="ascii").strip()
        return int(value, 0)
    except (OSError, ValueError):
        return None


def _detect_ram() -> _RamMeasurement:
    total_mb: int | None = None
    available_mb: int | None = None

    try:
        with open("/proc/meminfo", encoding="ascii") as stream:
            for line in stream:
                key, _, value = line.partition(":")
                if key == "MemTotal":
                    total_mb = int(value.split()[0]) // 1024
                elif key == "MemAvailable":
                    available_mb = int(value.split()[0]) // 1024
                if total_mb is not None and available_mb is not None:
                    break
    except (OSError, ValueError, IndexError):
        pass

    if total_mb is None:
        try:
            total_mb = int(
                os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1048576
            )
        except (AttributeError, OSError, ValueError):
            total_mb = None

    if total_mb is None or total_mb <= 0:
        raise RuntimeError("unable to detect total system RAM")

    if available_mb is None:
        available_mb = total_mb
    return _RamMeasurement(total_mb, min(total_mb, max(0, available_mb)))


def _detect_nvidia(timeout_seconds: float) -> list[GPUDevice]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=max(0.1, timeout_seconds),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    devices: list[GPUDevice] = []
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) < 3:
            continue
        try:
            total_mb = int(row[1].strip())
            available_mb = int(row[2].strip())
        except ValueError:
            total_mb = available_mb = None
        devices.append(
            GPUDevice(
                name=row[0].strip() or "NVIDIA GPU",
                vendor="nvidia",
                total_memory_mb=total_mb,
                available_memory_mb=available_mb,
                memory_kind="dedicated",
                detection_source="nvidia-smi",
            )
        )
    return devices


def detect_gpu_devices(*, timeout_seconds: float = 1.0) -> tuple[GPUDevice, ...]:
    """Best-effort GPU inventory; unknown memory remains unknown, never zero-filled."""
    devices = _detect_nvidia(timeout_seconds)
    nvidia_smi_vendors = {device.vendor for device in devices}

    # Linux DRM exposes PCI vendor IDs and, on supported AMD cards, VRAM counters.
    for device_path in glob.glob("/sys/class/drm/card[0-9]*/device"):
        vendor_id = _read_int(Path(device_path) / "vendor")
        device_id = _read_int(Path(device_path) / "device")
        vendor = {
            0x1002: "amd",
            0x10DE: "nvidia",
            0x8086: "intel",
        }.get(vendor_id)
        if vendor is None or vendor in nvidia_smi_vendors:
            continue

        total_bytes = _read_int(Path(device_path) / "mem_info_vram_total")
        used_bytes = _read_int(Path(device_path) / "mem_info_vram_used")
        total_mb = total_bytes // 1048576 if total_bytes is not None else None
        available_mb = (
            max(0, total_bytes - used_bytes) // 1048576
            if total_bytes is not None and used_bytes is not None
            else None
        )
        memory_kind = (
            "dedicated"
            if total_mb is not None
            else "shared"
            if vendor == "intel"
            else "unknown"
        )
        device_label = f"{vendor.upper()} GPU"
        if device_id is not None:
            device_label += f" ({device_id:#06x})"
        devices.append(
            GPUDevice(
                name=device_label,
                vendor=vendor,
                total_memory_mb=total_mb,
                available_memory_mb=available_mb,
                memory_kind=memory_kind,
                detection_source="linux-drm-sysfs",
            )
        )
    return tuple(devices)


def detect_hardware(
    *,
    include_gpu: bool = False,
    gpu_timeout_seconds: float = 1.0,
    disk_path: str | os.PathLike[str] | None = None,
    execution_backends: Iterable[str] = ("cpu",),
    backend_features: Iterable[str] = (),
) -> HardwareSnapshot:
    """Detect host resources without assuming that a detected GPU has a usable backend.

    GPU probing is opt-in. The caller must separately report execution backends
    actually initialized by the application (for example, a Vulkan or CUDA backend).
    """
    ram = _detect_ram()
    devices = detect_gpu_devices(timeout_seconds=gpu_timeout_seconds) if include_gpu else ()
    dedicated = [
        device
        for device in devices
        if device.memory_kind == "dedicated" and device.available_memory_mb is not None
    ]
    # Use the largest individual device; never add separate GPUs as if VRAM were unified.
    primary = max(dedicated, key=lambda item: item.available_memory_mb or 0, default=None)

    disk_free_mb = None
    if disk_path is not None:
        disk_free_mb = shutil.disk_usage(disk_path).free // 1048576

    backends = frozenset(str(item).lower() for item in execution_backends)
    if not backends:
        raise ValueError("execution_backends cannot be empty")

    return HardwareSnapshot(
        ram_total_mb=ram.total_mb,
        ram_available_mb=ram.available_mb,
        vram_total_mb=primary.total_memory_mb if primary else None,
        vram_available_mb=primary.available_memory_mb if primary else None,
        cpu_cores=os.cpu_count() or 1,
        backend_features=frozenset(str(item) for item in backend_features),
        execution_backends=backends,
        platform_id=platform.system().lower(),
        disk_free_mb=disk_free_mb,
        gpu_devices=devices,
    )


ULTRA_LIGHT_QUANTIZATION = QuantizationPolicy(
    preferred=("Q4_0", "Q3_K_M", "Q2_K", "Q4_K_M"),
    low_memory_preferred=("Q3_K_M", "Q2_K", "Q4_0"),
    low_memory_threshold_mb=4096,
)
LOW_MEMORY_QUANTIZATION = QuantizationPolicy(
    preferred=("Q4_K_M", "Q4_0", "Q5_K_M"),
    low_memory_preferred=("Q4_K_M", "Q4_0", "Q3_K_M", "Q2_K"),
    low_memory_threshold_mb=8192,
)
QUALITY_QUANTIZATION = QuantizationPolicy(
    preferred=("Q6_K", "Q8_0", "Q5_K_M", "Q4_K_M"),
    low_memory_preferred=("Q5_K_M", "Q4_K_M", "Q4_0"),
    low_memory_threshold_mb=8192,
)

CANONICAL_PROFILES = (
    HardwareProfile(
        "ultra_light", 1536, 0.35, 1024, 1, ("cpu",), 0, ULTRA_LIGHT_QUANTIZATION,
        description="Contenção extrema para hosts com pouca RAM; CPU-first.",
        min_context_tokens=512, priorities=("memory", "reliability"),
        max_cpu_threads=2, benchmark_allowed=("none", "quick"),
    ),
    HardwareProfile(
        "minimal", 2048, 0.55, 2048, 1, ("cpu", "gpu"), 0, LOW_MEMORY_QUANTIZATION,
        description="Prioriza contenção de memória em máquinas modestas.",
        min_context_tokens=1024, priorities=("memory", "reliability", "latency"),
        max_cpu_threads=4,
    ),
    HardwareProfile(
        "balanced", 4096, 0.65, 4096, 1, ("gpu", "cpu"), 0, LOW_MEMORY_QUANTIZATION,
        description="Equilíbrio entre qualidade, latência e uso de memória.",
        min_context_tokens=2048, max_cpu_threads=8,
    ),
    HardwareProfile(
        "performance", 8192, 0.75, 8192, 2, ("gpu", "cpu"), 0, QUALITY_QUANTIZATION,
        description="Prioriza latência com recursos suficientes.",
        min_context_tokens=4096, priorities=("latency", "quality", "memory"),
        max_cpu_threads=16,
    ),
    HardwareProfile(
        "max_quality", 16384, 0.80, 16384, 4, ("gpu", "cpu"), 0, QUALITY_QUANTIZATION,
        description="Prioriza qualidade e contexto em workstations.",
        min_context_tokens=8192, max_cpu_threads=16,
    ),
)


def serialize_hardware_profile(profile: HardwareProfile) -> dict[str, object]:
    """Public serializer used to keep JSON examples and Python presets identical."""
    return profile.to_dict()


def _reasons(profile: HardwareProfile, hw: HardwareSnapshot) -> list[str]:
    out: list[str] = []
    if hw.ram_total_mb < profile.min_ram_mb or hw.ram_available_mb < profile.min_ram_mb:
        out.append(f"{profile.profile_id}: RAM abaixo do mínimo de {profile.min_ram_mb} MiB")
    if profile.min_vram_mb and (
        hw.vram_available_mb is None or hw.vram_available_mb < profile.min_vram_mb
    ):
        out.append(f"{profile.profile_id}: VRAM ausente ou insuficiente")
    if not set(profile.preferred_backends).intersection(hw.execution_backends):
        out.append(f"{profile.profile_id}: backend incompatível")
    return out


def select_profile(hw: HardwareSnapshot, preferred: str | None = None) -> HardwareProfile:
    profiles = {profile.profile_id: profile for profile in CANONICAL_PROFILES}
    if preferred is not None and preferred not in profiles:
        raise ValueError(f"unknown hardware profile: {preferred}")
    eligible = [profile for profile in CANONICAL_PROFILES if not _reasons(profile, hw)]
    if preferred and any(profile.profile_id == preferred for profile in eligible):
        return profiles[preferred]
    return eligible[-1] if eligible else profiles["ultra_light"]


def _select_quantization(
    policy: QuantizationPolicy,
    hw: HardwareSnapshot,
    supported_quantizations: Iterable[str] | None,
) -> str | None:
    if supported_quantizations is None:
        return None
    supported = {item.upper() for item in supported_quantizations}
    return next(
        (
            candidate
            for candidate in policy.candidates_for(hw.ram_available_mb)
            if candidate.upper() in supported
        ),
        None,
    )


def build_compatibility_report(
    hw: HardwareSnapshot,
    requirements: ResourceRequirements = ResourceRequirements(),
    preferred_profile: str | None = None,
    benchmark_mode: BenchmarkMode | str = BenchmarkMode.NONE,
    benchmark: Callable[[str], Mapping[str, float]] | None = None,
    *,
    protection_mode: ProtectionMode | str = ProtectionMode.ADAPTIVE,
    supported_quantizations: Iterable[str] | None = None,
) -> CompatibilityReport:
    """Create a plan; benchmarks and backend-specific choices require explicit input."""
    mode = ProtectionMode(protection_mode)
    mode_benchmark = BenchmarkMode(benchmark_mode)
    reasons: list[str] = []
    fallbacks: list[str] = []

    if hw.ram_total_mb < requirements.min_ram_mb or hw.ram_available_mb < requirements.min_ram_mb:
        reasons.append("RAM abaixo do requisito mínimo do pacote")
    if requirements.min_vram_mb and (
        hw.vram_available_mb is None or hw.vram_available_mb < requirements.min_vram_mb
    ):
        reasons.append("VRAM necessária, mas ausente ou insuficiente")
    if requirements.min_disk_mb:
        if hw.disk_free_mb is None:
            reasons.append("espaço livre em disco desconhecido para requisito obrigatório")
        elif hw.disk_free_mb < requirements.min_disk_mb:
            reasons.append("espaço livre em disco abaixo do requisito mínimo")
    missing = set(requirements.required_features) - set(hw.backend_features)
    if missing:
        reasons.append("Recursos de backend ausentes: " + ", ".join(sorted(missing)))
    if not set(requirements.supported_execution).intersection(hw.execution_backends):
        reasons.append("Nenhum backend aceito está disponível")

    profile = select_profile(hw, preferred_profile)
    profile_failures = _reasons(profile, hw)
    if profile_failures:
        reasons.extend(profile_failures)
    if preferred_profile and profile.profile_id != preferred_profile:
        fallbacks.append(
            f"perfil {preferred_profile} indisponível; usando {profile.profile_id}"
        )
        if mode is ProtectionMode.PROTECTED:
            reasons.append(f"modo protegido: perfil solicitado {preferred_profile} não é elegível")

    if requirements.min_context_tokens > profile.context_tokens:
        reasons.append("contexto mínimo exigido excede o contexto do perfil selecionado")

    selected_backend = next(
        (backend for backend in profile.preferred_backends if backend in hw.execution_backends),
        next(iter(sorted(hw.execution_backends))),
    )
    budget = ResourceBudget(
        ram_limit_mb=int(hw.ram_available_mb * profile.max_ram_fraction),
        vram_limit_mb=hw.vram_available_mb or 0,
        context_tokens=max(requirements.min_context_tokens, profile.context_tokens),
        parallelism=min(profile.parallelism, max(1, hw.cpu_cores)),
        selected_backend=selected_backend,
        cpu_threads=min(profile.max_cpu_threads, max(1, hw.cpu_cores)),
    )

    if hw.vram_available_mb is None or hw.vram_available_mb == 0:
        fallbacks.append("VRAM desconhecida ou indisponível; usar apenas backend CPU registrado")
    if profile.profile_id in {"ultra_light", "minimal"}:
        fallbacks.append("desativar componentes opcionais e limitar novas tarefas concorrentes")
    absolute_floor_failed = (
        hw.ram_total_mb < 1536 or hw.ram_available_mb < 1536
    )
    if absolute_floor_failed:
        reasons.append(
            "host abaixo do piso absoluto de 1536 MiB de RAM total e disponível"
        )
        fallbacks.extend(
            (
                "fechar aplicativos e serviços que não estejam em uso e medir novamente",
                "descarregar modelos já residentes no backend e repetir a avaliação",
                "usar um computador com mais RAM; swap não substitui memória física para inferência",
            )
        )
    if budget.ram_limit_mb < requirements.min_ram_mb:
        fallbacks.append("buscar artefato alternativo validado; não violar requisito mínimo")

    quantization = _select_quantization(
        profile.quantization_policy, hw, supported_quantizations
    )
    if supported_quantizations is None:
        fallbacks.append(
            "quantização não selecionada: backend ainda não declarou formatos suportados"
        )
    elif quantization is None:
        fallbacks.append("nenhum candidato de quantização do perfil é suportado pelo backend")

    benchmark_result = None
    if mode_benchmark is not BenchmarkMode.NONE:
        if benchmark is None:
            fallbacks.append("benchmark solicitado sem executor; seleção permanece heurística")
        else:
            benchmark_result = dict(benchmark(mode_benchmark.value))

    compatible = not reasons
    activation_allowed = compatible or (
        mode is ProtectionMode.PERMISSIVE and not absolute_floor_failed
    )
    if not compatible and mode is ProtectionMode.PERMISSIVE and activation_allowed:
        fallbacks.append(
            "modo permissivo: tentativa autorizada apesar das incompatibilidades reportadas"
        )

    if compatible:
        user_message = (
            f"Configuração compatível: perfil {profile.profile_id}, "
            f"contexto até {budget.context_tokens} tokens e "
            f"{budget.cpu_threads} thread(s) de CPU."
        )
        recommendations: tuple[str, ...] = ()
    elif absolute_floor_failed:
        user_message = (
            "O AILocal Universal bloqueou a carga porque a memória disponível "
            "está abaixo do piso mínimo de 1,5 GiB. Continuar nessas condições "
            "pode provocar encerramento do processo ou travamento do sistema."
        )
        recommendations = (
            "Feche aplicativos pesados e serviços desnecessários.",
            "Descarregue modelos que já estejam carregados no Ollama.",
            "Tente novamente após a memória disponível superar 1,5 GiB.",
            "Use um modelo menor/quantizado já instalado ou aumente a RAM física.",
        )
    else:
        user_message = (
            "A configuração solicitada não atende aos requisitos de hardware "
            "ou backend. A ativação foi bloqueada pelo modo de proteção."
        )
        recommendations = tuple(fallbacks) or (
            "Escolha um perfil mais econômico ou ajuste os requisitos do pacote.",
        )

    return CompatibilityReport(
        compatible=compatible,
        selected_profile=profile.profile_id,
        budget=budget,
        reasons=tuple(dict.fromkeys(reasons)),
        fallbacks=tuple(dict.fromkeys(fallbacks)),
        benchmark_mode=mode_benchmark.value,
        benchmark_result=benchmark_result,
        activation_allowed=activation_allowed,
        protection_mode=mode.value,
        eligible_profiles=tuple(
            candidate.profile_id
            for candidate in CANONICAL_PROFILES
            if not _reasons(candidate, hw)
        ),
        quantization_candidate=quantization,
        user_message=user_message,
        recommendations=recommendations,
    )


class AdaptiveResourceManager:
    """Hysteresis-based policy evaluator; it recommends actions but applies none."""

    def __init__(
        self,
        *,
        constrained_threshold: float = 0.25,
        critical_threshold: float = 0.12,
        emergency_threshold: float = 0.07,
        recovery_threshold: float = 0.32,
    ) -> None:
        thresholds = (
            emergency_threshold,
            critical_threshold,
            constrained_threshold,
            recovery_threshold,
        )
        if not all(0 < value < 1 for value in thresholds):
            raise ValueError("pressure thresholds must be between 0 and 1")
        if not (
            emergency_threshold < critical_threshold
            < constrained_threshold < recovery_threshold
        ):
            raise ValueError(
                "thresholds must satisfy emergency < critical < constrained < recovery"
            )
        self.constrained_threshold = constrained_threshold
        self.critical_threshold = critical_threshold
        self.emergency_threshold = emergency_threshold
        self.recovery_threshold = recovery_threshold
        self._pressure = ResourcePressure.NORMAL

    @property
    def pressure(self) -> ResourcePressure:
        return self._pressure

    def evaluate(
        self,
        snapshot: HardwareSnapshot,
        *,
        active_parallelism: int = 1,
        active_context_tokens: int = 2048,
    ) -> DynamicResourceDecision:
        if active_parallelism < 1 or active_context_tokens < 1:
            raise ValueError("active resource values must be positive")
        fraction = snapshot.ram_available_mb / snapshot.ram_total_mb

        if fraction <= self.emergency_threshold:
            candidate = ResourcePressure.EMERGENCY
        elif fraction <= self.critical_threshold:
            candidate = ResourcePressure.CRITICAL
        elif fraction <= self.constrained_threshold:
            candidate = ResourcePressure.CONSTRAINED
        else:
            candidate = ResourcePressure.NORMAL

        severity = {
            ResourcePressure.NORMAL: 0,
            ResourcePressure.CONSTRAINED: 1,
            ResourcePressure.CRITICAL: 2,
            ResourcePressure.EMERGENCY: 3,
        }
        if severity[candidate] > severity[self._pressure]:
            self._pressure = candidate
        elif candidate is ResourcePressure.NORMAL:
            if fraction >= self.recovery_threshold:
                self._pressure = ResourcePressure.NORMAL
            # Keep the prior state until recovery threshold is crossed.
        elif severity[candidate] < severity[self._pressure]:
            if fraction >= self.recovery_threshold:
                self._pressure = candidate

        pressure = self._pressure
        actions: list[str] = []
        parallelism_limit = None
        context_target = None
        pause_new_loads = False
        reject_new_loads = False
        suspend_optional_work = False

        if pressure is ResourcePressure.CONSTRAINED:
            actions.append("evitar novas cargas pesadas")
            if active_parallelism > 1:
                parallelism_limit = max(1, active_parallelism - 1)
                actions.append("reduzir concorrência para novas solicitações")
            context_target = max(512, int(active_context_tokens * 0.75))
        elif pressure is ResourcePressure.CRITICAL:
            pause_new_loads = True
            parallelism_limit = 1
            context_target = max(512, int(active_context_tokens * 0.5))
            actions.extend(
                (
                    "pausar novas cargas de modelos e plugins",
                    "limitar novas solicitações a uma tarefa por vez",
                    "reduzir contexto de sessões futuras quando permitido",
                    "desativar componentes opcionais ainda não utilizados",
                )
            )
        elif pressure is ResourcePressure.EMERGENCY:
            pause_new_loads = True
            reject_new_loads = True
            suspend_optional_work = True
            parallelism_limit = 1
            context_target = max(512, int(active_context_tokens * 0.5))
            actions.extend(
                (
                    "recusar novas cargas até a memória se recuperar",
                    "suspender tarefas opcionais que ainda não começaram",
                    "solicitar ao backend a liberação segura de componentes opcionais",
                )
            )

        if pressure is ResourcePressure.NORMAL:
            actions.append("sem redução dinâmica necessária")

        return DynamicResourceDecision(
            pressure=pressure,
            available_fraction=fraction,
            pause_new_loads=pause_new_loads,
            reject_new_loads=reject_new_loads,
            suspend_optional_work=suspend_optional_work,
            parallelism_limit=parallelism_limit,
            recommended_context_tokens=context_target,
            actions=tuple(actions),
        )
