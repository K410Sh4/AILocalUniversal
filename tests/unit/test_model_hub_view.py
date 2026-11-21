from PySide6.QtWidgets import QApplication

from app.views.model_hub_view import ModelHubView
from model_hub.compatibility import CompatibilityResult, CompatibilityStatus
from model_hub.contracts import ModelArtifact, ModelRecord
from model_hub.hardware import AcceleratorInfo, HardwareProfile


def test_model_hub_view_displays_models_and_unknown_metadata() -> None:
    app = QApplication.instance() or QApplication([])
    view = ModelHubView()
    record = ModelRecord(
        record_id="ollama:qwen3:4b",
        display_name="qwen3:4b",
        family="qwen3",
        category="general",
        capabilities=("chat", "streaming"),
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference="qwen3:4b",
                installed=True,
                size_bytes=1024,
            ),
        ),
    )
    hardware = HardwareProfile(
        operating_system="Linux",
        architecture="x86_64",
        cpu_model="Test CPU",
        cpu_logical_cores=8,
        ram_total_bytes=16 * 1024**3,
        ram_available_bytes=8 * 1024**3,
        disk_free_bytes=20 * 1024**3,
        accelerators=(
            AcceleratorInfo(
                vendor="AMD",
                name="Radeon Test GPU",
                driver="amdgpu",
                vram_total_bytes=8 * 1024**3,
                vram_available_bytes=6 * 1024**3,
            ),
        ),
    )

    view.set_data(
        hardware,
        [record],
        {
            record.record_id: CompatibilityResult(
                CompatibilityStatus.UNKNOWN,
                ("Requisitos não verificados.",),
            )
        },
        runtime_available={"ollama"},
    )

    assert view.table.rowCount() == 1
    assert view.table.item(0, 0).text() == "qwen3:4b"
    assert view.table.item(0, 5).text() == "Não avaliado"
    details = view.details.toPlainText().casefold()
    assert "id: ollama:qwen3:4b" in details
    assert "não verificada" in details
    assert "não há requisitos" in details
    assert "radeon test gpu" in view.hardware_label.text().casefold()

    view.close()
    app.processEvents()
