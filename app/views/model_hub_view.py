"""Interface inicial do NeuralModel Hub."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.views.models_view import format_size
from model_hub.catalog import (
    CATALOG_CATEGORIES,
    CatalogDocument,
    CatalogEntry,
    CatalogVariant,
    current_platform,
)
from model_hub.compatibility import CompatibilityResult, CompatibilityStatus
from model_hub.contracts import ModelRecord
from model_hub.hardware import HardwareProfile


class ModelHubView(QWidget):
    """Apresenta inventário local e catálogo remoto com gestão de modelos."""

    refresh_requested = Signal()
    catalog_refresh_requested = Signal()
    install_requested = Signal(str)
    cancel_download_requested = Signal()
    delete_requested = Signal(str)

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
        self.resource_label = QLabel(
            "Seletor adaptativo aguardando uma avaliação de recursos."
        )
        self.resource_label.setWordWrap(True)

        self.remove_button = QPushButton("Remover modelo selecionado")
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self._request_delete_selected)

        self.local_tab = QWidget()
        local_layout = QVBoxLayout(self.local_tab)
        local_layout.addWidget(self.resource_label)
        local_layout.addWidget(self.table, 1)
        local_layout.addWidget(self.details)
        local_layout.addWidget(self.remove_button)

        self.catalog_search = QLineEdit()
        self.catalog_search.setPlaceholderText(
            "Pesquisar modelos, família, desenvolvedor ou capacidade…"
        )
        self.catalog_search.textChanged.connect(self._render_catalog)
        self.category_filter = QComboBox()
        self.category_filter.addItem("Todas as categorias", "")
        for key, label in CATALOG_CATEGORIES.items():
            self.category_filter.addItem(label, key)
        self.category_filter.currentIndexChanged.connect(self._render_catalog)
        self.catalog_refresh_button = QPushButton("Atualizar catálogo online")
        self.catalog_refresh_button.clicked.connect(self.catalog_refresh_requested.emit)
        filters = QHBoxLayout()
        filters.addWidget(self.catalog_search, 1)
        filters.addWidget(self.category_filter)
        filters.addWidget(self.catalog_refresh_button)

        self.catalog_table = QTableWidget(0, 4)
        self.catalog_table.setHorizontalHeaderLabels(
            ["Modelo", "Categorias", "Variantes Ollama", "Tamanho publicado"]
        )
        self.catalog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.catalog_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.catalog_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.catalog_table.verticalHeader().setVisible(False)
        self.catalog_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in range(1, 4):
            self.catalog_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.catalog_table.itemSelectionChanged.connect(self._show_catalog_details)
        self.catalog_status_label = QLabel("Catálogo online ainda não consultado.")
        self.catalog_details = QPlainTextEdit()
        self.catalog_details.setReadOnly(True)
        self.catalog_details.setMaximumHeight(145)
        self.variant_combo = QComboBox()
        self.variant_combo.currentIndexChanged.connect(self._update_variant_state)
        self.source_button = QPushButton("Abrir fonte")
        self.source_button.setEnabled(False)
        self.source_button.clicked.connect(self._open_selected_source)
        self.install_button = QPushButton("Baixar e instalar")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._request_install_selected)
        self.cancel_button = QPushButton("Cancelar download")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_download_requested.emit)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Aguardando download")
        self.install_status_label = QLabel("Nenhum download em andamento.")
        install_row = QHBoxLayout()
        install_row.addWidget(QLabel("Variante / quantização:"))
        install_row.addWidget(self.variant_combo, 1)
        install_row.addWidget(self.source_button)
        install_row.addWidget(self.install_button)
        install_row.addWidget(self.cancel_button)

        self.catalog_tab = QWidget()
        catalog_layout = QVBoxLayout(self.catalog_tab)
        catalog_layout.addLayout(filters)
        catalog_layout.addWidget(self.catalog_status_label)
        catalog_layout.addWidget(self.catalog_table, 1)
        catalog_layout.addWidget(self.catalog_details)
        catalog_layout.addLayout(install_row)
        catalog_layout.addWidget(self.progress_bar)
        catalog_layout.addWidget(self.install_status_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.local_tab, "Instalados e hardware")
        self.tabs.addTab(self.catalog_tab, "Catálogo online")

        layout = QVBoxLayout(self)
        header = QGroupBox("Perfil deste computador")
        header_layout = QVBoxLayout(header)
        header_layout.addWidget(self.hardware_label)
        header_layout.addWidget(self.refresh_button)
        layout.addWidget(header)
        layout.addWidget(self.status_label)
        layout.addWidget(self.tabs, 1)

        self._records: list[ModelRecord] = []
        self._compatibility: dict[str, CompatibilityResult] = {}
        self._row_record_ids: list[str] = []
        self._catalog_document: CatalogDocument | None = None
        self._catalog_entries: list[CatalogEntry] = []
        self._visible_entries: list[CatalogEntry] = []
        self._installed_refs: set[str] = set()
        self._selected_catalog_entry: CatalogEntry | None = None
        self._catalog_busy = False
        self._download_busy = False

    @staticmethod
    def _format_bytes(value: int | None) -> str:
        return format_size(value)

    def set_resource_recommendation(self, message: str) -> None:
        """Exibe a justificativa da última decisão do seletor adaptativo."""
        self.resource_label.setText(message.strip() or "Nenhuma recomendação disponível.")

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
        self._installed_refs = {
            artifact.reference.casefold()
            for record in records
            for artifact in record.artifacts
            if artifact.installed and artifact.runtime == "ollama"
        }
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
        self._render_catalog()

    def _show_selected_details(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.details.clear()
            self.remove_button.setEnabled(False)
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

        selected_ref = next(
            (
                item.reference for item in record.artifacts
                if item.runtime == "ollama" and item.installed
            ),
            None,
        )
        self.remove_button.setEnabled(bool(selected_ref) and not self._download_busy)

    def _request_delete_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row >= len(self._row_record_ids):
            return
        record = next(
            (item for item in self._records if item.record_id == self._row_record_ids[row]),
            None,
        )
        if record is None:
            return
        reference = next(
            (
                item.reference for item in record.artifacts
                if item.runtime == "ollama" and item.installed
            ),
            None,
        )
        if reference:
            self.delete_requested.emit(reference)

    def set_catalog_data(
        self, document: CatalogDocument, installed_refs: set[str]
    ) -> None:
        self._catalog_document = document
        self._catalog_entries = list(document.entries)
        self._installed_refs = {item.casefold() for item in installed_refs}
        warning = f" • {document.warning}" if document.warning else ""
        origin = "online" if document.source == "online" else "fallback local"
        self.catalog_status_label.setText(
            f"{len(document.entries)} modelos • catálogo {document.catalog_version} • "
            f"atualizado {document.updated_at} • fonte {origin}{warning}"
        )
        self._render_catalog()

    def set_catalog_loading(self, loading: bool, message: str | None = None) -> None:
        self._catalog_busy = loading
        self.catalog_refresh_button.setEnabled(not loading and not self._download_busy)
        if message:
            self.catalog_status_label.setText(message)

    def _render_catalog(self, *_args) -> None:
        category = str(self.category_filter.currentData() or "")
        query = self.catalog_search.text().strip().casefold()
        self._visible_entries = []
        for entry in self._catalog_entries:
            if category and category not in entry.categories:
                continue
            searchable = " ".join(
                (entry.display_name, entry.family, entry.summary, entry.publisher,
                 " ".join(entry.capabilities), " ".join(entry.categories))
            ).casefold()
            if query and query not in searchable:
                continue
            self._visible_entries.append(entry)

        self.catalog_table.setRowCount(len(self._visible_entries))
        for row, entry in enumerate(self._visible_entries):
            categories = ", ".join(
                CATALOG_CATEGORIES.get(item, item) for item in entry.categories
            )
            variants = ", ".join(item.reference for item in entry.variants)
            sizes = ", ".join(
                item.size_label or "tamanho não publicado" for item in entry.variants
            )
            state = (
                "instalado" if any(
                    item.reference.casefold() in self._installed_refs
                    for item in entry.variants
                ) else (
                    "disponível" if any(item.available_on() for item in entry.variants)
                    else "sem suporte nesta plataforma"
                )
            )
            for column, value in enumerate(
                (entry.display_name, categories, variants, f"{sizes} • {state}")
            ):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.catalog_table.setItem(row, column, item)
        if self._visible_entries:
            self.catalog_table.selectRow(0)
            self._show_catalog_details()
        else:
            self._selected_catalog_entry = None
            self.catalog_details.setPlainText(
                "Nenhum modelo corresponde aos filtros. Uma categoria vazia significa "
                "que ainda não há pacote Ollama curado para ela."
            )
            self.variant_combo.clear()
            self.source_button.setEnabled(False)
            self.install_button.setEnabled(False)

    def _show_catalog_details(self) -> None:
        rows = self.catalog_table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self._visible_entries):
            self._selected_catalog_entry = None
            self.install_button.setEnabled(False)
            self.source_button.setEnabled(False)
            return
        entry = self._visible_entries[rows[0].row()]
        self._selected_catalog_entry = entry
        categories = ", ".join(
            CATALOG_CATEGORIES.get(item, item) for item in entry.categories
        )
        license_label = (
            f"{entry.license_name} (verificada na fonte)"
            if entry.license_verified
            else "não verificada — confira a licença antes do uso"
        )
        variants = "\\n".join(
            f"- {item.reference}: {item.size_label or 'tamanho não publicado'}; "
            f"{item.quantization or 'quantização não informada'}"
            for item in entry.variants
        )
        self.catalog_details.setPlainText(
            f"{entry.display_name} — {entry.family}\\n{entry.summary}\\n"
            f"Desenvolvedor: {entry.publisher}\\nCategorias: {categories}\\n"
            f"Capacidades: {', '.join(entry.capabilities)}\\n"
            f"Modalidades: {', '.join(entry.modalities)}\\n"
            f"Parâmetros: {entry.parameter_count or 'não informado'}\\n"
            f"Contexto: {entry.context_window or 'não informado'}\\n"
            f"Licença: {license_label}\\nVariantes:\\n{variants}\\n"
            f"Fonte: {entry.source_url}"
        )
        self.variant_combo.blockSignals(True)
        self.variant_combo.clear()
        for variant in entry.variants:
            label = f"{variant.reference} • {variant.size_label or 'tamanho não publicado'}"
            if variant.quantization:
                label += f" • {variant.quantization}"
            if not variant.available_on():
                label += " • indisponível nesta plataforma"
            self.variant_combo.addItem(label, variant.reference)
        self.variant_combo.blockSignals(False)
        self.source_button.setEnabled(True)
        self._update_variant_state()

    def _selected_variant(self) -> CatalogVariant | None:
        entry = self._selected_catalog_entry
        reference = str(self.variant_combo.currentData() or "")
        if entry is None or not reference:
            return None
        return next((item for item in entry.variants if item.reference == reference), None)

    def _update_variant_state(self, *_args) -> None:
        variant = self._selected_variant()
        available = (
            variant is not None and variant.available_on()
            and not self._catalog_busy and not self._download_busy
        )
        self.install_button.setEnabled(bool(available))
        if variant is not None and not variant.available_on():
            self.install_button.setToolTip(
                variant.install_note or f"Não suportado em {current_platform()}."
            )
        elif variant is not None:
            self.install_button.setText(
                "Atualizar / reinstalar"
                if variant.reference.casefold() in self._installed_refs
                else "Baixar e instalar"
            )

    def _request_install_selected(self) -> None:
        variant = self._selected_variant()
        if (
            variant is not None and variant.available_on()
            and not self._download_busy and not self._catalog_busy
        ):
            self.install_requested.emit(variant.reference)

    def _open_selected_source(self) -> None:
        if self._selected_catalog_entry is not None:
            QDesktopServices.openUrl(QUrl(self._selected_catalog_entry.source_url))

    def set_installation_busy(self, busy: bool, message: str | None = None) -> None:
        self._download_busy = busy
        self.cancel_button.setEnabled(busy)
        self.catalog_refresh_button.setEnabled(not busy and not self._catalog_busy)
        self.catalog_table.setEnabled(not busy)
        self.variant_combo.setEnabled(not busy)
        self.install_button.setEnabled(
            not busy and self._selected_variant() is not None
            and self._selected_variant().available_on()
        )
        if busy:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("Download em andamento")
        elif self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Pronto")
        if message:
            self.install_status_label.setText(message)
        if not busy:
            self._update_variant_state()
            self._show_selected_details()

    def set_installation_progress(self, event: object) -> None:
        if not isinstance(event, dict):
            return
        status = str(event.get("status") or "Download em andamento")
        total = event.get("total")
        completed = event.get("completed")
        if (
            isinstance(total, int) and not isinstance(total, bool) and total > 0
            and isinstance(completed, int) and not isinstance(completed, bool)
        ):
            value = max(0, min(100, int(completed * 100 / total)))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)
            self.progress_bar.setFormat(f"{value}% desta camada")
            self.install_status_label.setText(
                f"{status} • {self._format_bytes(completed)} / {self._format_bytes(total)}"
            )
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat(status)
            self.install_status_label.setText(status)

    def mark_installation_complete(self, message: str) -> None:
        self.set_installation_busy(False, message)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Concluído")
        self._render_catalog()

    def mark_installation_cancelled(self, message: str) -> None:
        self.set_installation_busy(False, message)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Cancelado")
