from model_hub.hardware import HardwareProfiler


def test_hardware_profiler_reads_linux_memory_and_gpu_sysfs(tmp_path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       16384000 kB\nMemAvailable:    8192000 kB\n",
        encoding="ascii",
    )
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("model name : Test CPU 9000\n", encoding="utf-8")

    drm = tmp_path / "drm"
    device = drm / "card1" / "device"
    device.mkdir(parents=True)
    (device / "vendor").write_text("0x1002\n", encoding="ascii")
    (device / "device").write_text("0x731f\n", encoding="ascii")
    (device / "product_name").write_text("Radeon Test GPU\n", encoding="utf-8")
    (device / "mem_info_vram_total").write_text("8589934592\n", encoding="ascii")
    (device / "mem_info_vram_used").write_text("1073741824\n", encoding="ascii")
    (device / "gpu_busy_percent").write_text("17\n", encoding="ascii")
    driver = tmp_path / "drivers" / "amdgpu"
    driver.mkdir(parents=True)
    (device / "driver").symlink_to(driver, target_is_directory=True)

    profile = HardwareProfiler(
        meminfo_path=meminfo,
        cpuinfo_path=cpuinfo,
        drm_root=drm,
        data_path=tmp_path,
    ).probe()

    assert profile.ram_total_bytes == 16_777_216_000
    assert profile.ram_available_bytes == 8_388_608_000
    assert profile.cpu_model == "Test CPU 9000"
    if profile.operating_system == "Linux":
        assert len(profile.accelerators) == 1
        gpu = profile.accelerators[0]
        assert gpu.vendor == "AMD"
        assert gpu.name == "Radeon Test GPU"
        assert gpu.driver == "amdgpu"
        assert gpu.vram_available_bytes == 7 * 1024**3
        assert gpu.gpu_busy_percent == 17


def test_hardware_profiler_handles_missing_proc_and_gpu_data(tmp_path) -> None:
    profile = HardwareProfiler(
        meminfo_path=tmp_path / "missing-meminfo",
        cpuinfo_path=tmp_path / "missing-cpuinfo",
        drm_root=tmp_path / "missing-drm",
        data_path=tmp_path,
    ).probe()

    assert profile.operating_system
    assert profile.architecture
    assert profile.accelerators == ()



def test_hardware_profiler_identifies_known_rx_5700_xt_subsystem(tmp_path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 16384000 kB\nMemAvailable: 8192000 kB\n", encoding="ascii")
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("model name : Test CPU\n", encoding="utf-8")
    drm = tmp_path / "drm"
    device = drm / "card0" / "device"
    device.mkdir(parents=True)
    (device / "vendor").write_text("0x1002\n", encoding="ascii")
    (device / "device").write_text("0x731f\n", encoding="ascii")
    (device / "subsystem_vendor").write_text("0x1002\n", encoding="ascii")
    (device / "subsystem_device").write_text("0x0b36\n", encoding="ascii")

    profile = HardwareProfiler(
        meminfo_path=meminfo,
        cpuinfo_path=cpuinfo,
        drm_root=drm,
        data_path=tmp_path,
    ).probe()

    if profile.operating_system == "Linux":
        assert len(profile.accelerators) == 1
        gpu = profile.accelerators[0]
        assert gpu.name == "AMD Radeon RX 5700 XT (Reference)"
        assert gpu.pci_device_id == "0x731f"
        assert gpu.pci_subsystem_vendor_id == "0x1002"
        assert gpu.pci_subsystem_device_id == "0x0b36"
