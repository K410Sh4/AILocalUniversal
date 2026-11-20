"""Interface inicial do NeuralModel Hub."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.views.models_view import format_size
from model_hub.compatibility import CompatibilityResult, CompatibilityStatus
from model_hub.contracts import ModelRecord
from model_hub.hardware import HardwareProfile


class ModelHubView(QWidget):
    """Apresenta inventário local e compatibilidade sem iniciar downloads."""

    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.hardware_label = QLabel("Perfil de hardware ainda não coletado.")
        self.hardware_label.setWordWrap(True)
        self.status_label = QLabel("Catálogo local ainda não consultado.")
        self.refresh_button = QPushButton("Atualizar hardware e modelos")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [
                "Modelo",
                "Categoria",
                "Runtime / artefato",
                "Capacidades",
                "Arquivo",
                "Compatibilidade",
            ]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(125)
        self.details.setPlaceholderText("Selecione um modelo para consultar seus metadados.")

        layout = QVBoxLayout(self)
        header = QGroupBox("Perfil deste computador")
        header_layout = QVBoxLayout(header)
        header_layout.addWidget(self.hardware_label)
        header_layout.addWidget(self.refresh_button)
        layout.addWidget(header)
        layout.addWidget(self.status_label)
        layout.addWidget(self.table, 1)
        detail_group = QGroupBox("Ficha e procedência")
        detail_layout = QVBoxLayout(detail_group)
        detail_layout.addWidget(self.details)
        layout.addWidget(detail_group)

        self._records: list[ModelRecord] = []
        self._compatibility: dict[str, CompatibilityResult] = {}
        self._row_record_ids: list[str] = []

    @staticmethod
    def _format_bytes(value: int | None) -> str:
        return format_size(value)

    def set_data(
        self,
        hardware: HardwareProfile,
        records: list[ModelRecord],
        compatibility: dict[str, CompatibilityResult],
        *,
        runtime_available: set[str],
        registry_warning: str | None = None,
    ) -> None:
        self._records = records
        self._compatibility = compatibility
        ram = (
            f"{self._format_bytes(hardware.ram_available_bytes)} disponíveis de "
            f"{self._format_bytes(hardware.ram_total_bytes)}"
        )
        cpu = hardware.cpu_model or hardware.architecture
        lines = [
            f"Sistema: {hardware.operating_system} / {hardware.architecture}",
            f"CPU: {cpu} • {hardware.cpu_logical_cores or '—'} thread(s) lógicas",
            f"RAM: {ram}",
            f"Disco livre: {self._format_bytes(hardware.disk_free_bytes)}",
        ]
        if hardware.accelerators:
            for item in hardware.accelerators:
                vram = (
                    f"{self._format_bytes(item.vram_available_bytes)} livres de "
                    f"{self._format_bytes(item.vram_total_bytes)}"
                )
                driver = item.driver or "driver não identificado"
                lines.append(f"GPU: {item.name} ({item.vendor}, {driver}) • VRAM: {vram}")
        else:
            lines.append("GPU: nenhum dispositivo detectado pelo método disponível.")
        self.hardware_label.setText("\n".join(lines))

        self.table.setRowCount(len(records))
        self._row_record_ids = []
        for row, record in enumerate(records):
            artifacts = [item for item in record.artifacts if item.installed]
            runtime_text = ", ".join(
                f"{item.runtime}: {item.reference}" for item in artifacts
            ) or "Não instalado"
            capabilities = ", ".join(record.capabilities) or "Não identificadas"
            artifact_size = sum(item.size_bytes or 0 for item in artifacts)
            result = compatibility.get(
                record.record_id,
                CompatibilityResult(CompatibilityStatus.UNKNOWN, ("Não avaliado.",)),
            )
            status_text = {
                CompatibilityStatus.COMPATIBLE: "Compatível",
                CompatibilityStatus.INCOMPATIBLE: "Incompatível",
                CompatibilityStatus.UNKNOWN: "Não avaliado",
            }[result.status]
            values = (
                record.display_name, record.category, runtime_text, capabilities,
                self._format_bytes(artifact_size) if artifacts else "—", status_text,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 5:
                    cell.setToolTip("\n".join(result.reasons))
                self.table.setItem(row, column, cell)
            self._row_record_ids.append(record.record_id)

        if registry_warning:
            self.status_label.setText(
                f"Aviso no catálogo: {registry_warning} — dados desta sessão não serão persistidos."
            )
        else:
            installed_count = sum(
                any(artifact.installed for artifact in record.artifacts)
                for record in records
            )
            unknown_count = sum(
                item.status is CompatibilityStatus.UNKNOWN
                for item in compatibility.values()
            )
            runtime_text = ", ".join(sorted(runtime_available)) or "nenhum confirmado"
            self.status_label.setText(
                f"{len(records)} ficha(s) • {installed_count} com artefato instalado • "
                f"{unknown_count} compatibilidade(s) não avaliada(s) • "
                f"Runtime(s) confirmado(s): {runtime_text}"
            )
        self.details.clear()
        if records:
            self.table.selectRow(0)
            # Qt may not emit itemSelectionChanged during initial population.
            self._show_selected_details()
        else:
            self.details.setPlainText(
                "Nenhum modelo foi descoberto. Inicie um runtime compatível "
                "e atualize o inventário."
            )

    def _show_selected_details(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.details.clear()
            return
        row = rows[0].row()
        if row >= len(self._row_record_ids):
            return
        record_id = self._row_record_ids[row]
        record = next((item for item in self._records if item.record_id == record_id), None)
        if record is None:
            return
        result = self._compatibility.get(
            record_id,
            CompatibilityResult(CompatibilityStatus.UNKNOWN, ("Não avaliado.",)),
        )
        license_label = (
            f"{record.license_name} (verificada)"
            if record.license_verified
            else "Desconhecida / não verificada"
        )
        requirements = record.resource_requirements
        if requirements is None or not requirements.verified:
            requirement_label = (
                "Não há requisitos de execução verificados. O tamanho do arquivo exibido "
                "é o tamanho do artefato no runtime, não a memória necessária para inferência."
            )
        else:
            requirement_label = (
                f"RAM mínima: {self._format_bytes(requirements.minimum_ram_bytes)}; "
                f"VRAM mínima: {self._format_bytes(requirements.minimum_vram_bytes)}. "
                f"Evidência: {requirements.evidence_url}"
            )
        artifacts = "\n".join(
            f"- {item.runtime}: {item.reference}; instalado={item.installed}; "
            f"digest={item.digest or 'não informado'}; "
            f"quantização={item.quantization or 'não informada'}"
            for item in record.artifacts
        ) or "Nenhum artefato associado."
        self.details.setPlainText(
            f"ID: {record.record_id}\n"
            f"Família: {record.family}\n"
            f"Categoria: {record.category}\n"
            f"Arquitetura: {record.architecture or 'não informada'}\n"
            f"Parâmetros: {record.parameter_count or 'não informados'}\n"
            f"Contexto: {record.context_window or 'não informado'}\n"
            f"Licença: {license_label}\n"
            f"Publicador: {record.publisher or 'não informado'}\n"
            f"Origem dos metadados: {record.metadata_source}\n"
            f"Fonte: {record.source_url or 'não cadastrada'}\n"
            f"Artefatos:\n{artifacts}\n"
            f"Compatibilidade: {result.status.value} — {'; '.join(result.reasons)}\n"
            f"Requisitos: {requirement_label}"
        )
