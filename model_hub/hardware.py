"""Perfil local de hardware, sem inferir backend de computação pelo driver."""

from __future__ import annotations

import os
import platform
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

_VENDOR_NAMES = {
    "0x1002": "AMD",
    "0x10de": "NVIDIA",
    "0x8086": "Intel",
    "0x1af4": "VirtIO",
}

# PCI subsystem IDs observed on the reference RX 5700 XT supplied by this
# device's board vendor. Unknown subsystem IDs intentionally remain generic.
_SUBSYSTEM_NAMES = {
    ("0x1002", "0x731f", "0x1002", "0x0b36"): "AMD Radeon RX 5700 XT (Reference)",
}


@dataclass(frozen=True, slots=True)
class AcceleratorInfo:
    """Dispositivo gráfico observado no sistema."""

    vendor: str
    name: str
    pci_vendor_id: str | None = None
    pci_device_id: str | None = None
    pci_subsystem_vendor_id: str | None = None
    pci_subsystem_device_id: str | None = None
    driver: str | None = None
    vram_total_bytes: int | None = None
    vram_used_bytes: int | None = None
    vram_available_bytes: int | None = None
    gpu_busy_percent: int | None = None


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    """Snapshot de recursos disponíveis no momento da coleta."""

    operating_system: str
    architecture: str
    cpu_model: str | None
    cpu_logical_cores: int | None
    ram_total_bytes: int | None
    ram_available_bytes: int | None
    disk_free_bytes: int | None
    accelerators: tuple[AcceleratorInfo, ...] = ()


class HardwareProfiler:
    """Coleta CPU/RAM/disco e, no Linux, GPUs expostas pelo sysfs do DRM."""

    def __init__(
        self,
        *,
        meminfo_path: Path = Path("/proc/meminfo"),
        cpuinfo_path: Path = Path("/proc/cpuinfo"),
        drm_root: Path = Path("/sys/class/drm"),
        data_path: Path | None = None,
    ) -> None:
        self.meminfo_path = meminfo_path
        self.cpuinfo_path = cpuinfo_path
        self.drm_root = drm_root
        self.data_path = data_path or Path.home()

    @staticmethod
    def _read_int(path: Path) -> int | None:
        try:
            value = path.read_text(encoding="ascii").strip()
            try:
                return int(value, 0)
            except ValueError:
                return int(value, 10)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _read_text(path: Path) -> str | None:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return value or None

    def _memory(self) -> tuple[int | None, int | None]:
        values: dict[str, int] = {}
        try:
            for line in self.meminfo_path.read_text(encoding="ascii").splitlines():
                match = re.match(
                    r"^(MemTotal|MemAvailable|MemFree|Buffers|Cached):\s+(\d+)\s+kB$",
                    line,
                )
                if match:
                    values[match.group(1)] = int(match.group(2)) * 1024
        except OSError:
            pass
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if available is None and total is not None:
            available = sum(values.get(key, 0) for key in ("MemFree", "Buffers", "Cached"))
        if total is None and hasattr(os, "sysconf"):
            try:
                total = int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
            except (OSError, ValueError, TypeError):
                pass
        return total, available

    def _cpu_model(self) -> str | None:
        try:
            lines = self.cpuinfo_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                key, separator, value = line.partition(":")
                if separator and key.strip().casefold() in {
                    "model name", "hardware", "processor name"
                } and value.strip():
                    return value.strip()[:200]
        except OSError:
            pass
        return platform.processor() or None

    def _accelerators(self) -> tuple[AcceleratorInfo, ...]:
        if platform.system() != "Linux" or not self.drm_root.exists():
            return ()
        devices: list[AcceleratorInfo] = []
        for card in sorted(self.drm_root.glob("card[0-9]*")):
            if not re.fullmatch(r"card\d+", card.name):
                continue
            device_path = card / "device"
            vendor_id = self._read_text(device_path / "vendor")
            if vendor_id is None:
                continue
            vendor_id = vendor_id.lower()
            vendor = _VENDOR_NAMES.get(vendor_id, f"PCI {vendor_id}")
            device_id = self._read_text(device_path / "device")
            subsystem_vendor_id = self._read_text(device_path / "subsystem_vendor")
            subsystem_device_id = self._read_text(device_path / "subsystem_device")
            normalized_device_id = device_id.lower() if device_id else None
            normalized_subsystem_vendor_id = (
                subsystem_vendor_id.lower() if subsystem_vendor_id else None
            )
            normalized_subsystem_device_id = (
                subsystem_device_id.lower() if subsystem_device_id else None
            )
            bus_id = device_path.resolve(strict=False).name
            product_name = self._read_text(device_path / "product_name")
            subsystem_name = _SUBSYSTEM_NAMES.get(
                (
                    vendor_id,
                    normalized_device_id,
                    normalized_subsystem_vendor_id,
                    normalized_subsystem_device_id,
                )
            )
            name = product_name or subsystem_name or f"{vendor} GPU ({bus_id})"
            driver_path = (device_path / "driver").resolve(strict=False)
            driver = driver_path.name if driver_path.name != "driver" else None
            total = self._read_int(device_path / "mem_info_vram_total")
            used = self._read_int(device_path / "mem_info_vram_used")
            free = max(total - used, 0) if total is not None and used is not None else None
            busy = self._read_int(device_path / "gpu_busy_percent")
            devices.append(
                AcceleratorInfo(
                    vendor=vendor,
                    name=name,
                    pci_vendor_id=vendor_id,
                    pci_device_id=normalized_device_id,
                    pci_subsystem_vendor_id=normalized_subsystem_vendor_id,
                    pci_subsystem_device_id=normalized_subsystem_device_id,
                    driver=driver,
                    vram_total_bytes=total,
                    vram_used_bytes=used,
                    vram_available_bytes=free,
                    gpu_busy_percent=busy if busy is not None and 0 <= busy <= 100 else None,
                )
            )
        return tuple(devices)

    def probe(self) -> HardwareProfile:
        ram_total, ram_available = self._memory()
        try:
            disk_free = shutil.disk_usage(self.data_path).free
        except OSError:
            disk_free = None
        return HardwareProfile(
            operating_system=platform.system() or "unknown",
            architecture=platform.machine() or "unknown",
            cpu_model=self._cpu_model(),
            cpu_logical_cores=os.cpu_count(),
            ram_total_bytes=ram_total,
            ram_available_bytes=ram_available,
            disk_free_bytes=disk_free,
            accelerators=self._accelerators(),
        )
