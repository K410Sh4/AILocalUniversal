"""Visualização do inventário de modelos Ollama."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engines.base import ModelInfo


def format_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "—"
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return "—"


class ModelsView(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.refresh_button = QPushButton("Atualizar")
        self.status_label = QLabel("Inventário ainda não consultado.")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Modelo", "Capacidades", "Tamanho", "Digest"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        top = QHBoxLayout()
        top.addWidget(self.status_label, 1)
        top.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)

    def set_models(self, models: list[ModelInfo], healthy: bool) -> None:
        self.table.setRowCount(len(models))
        for row, model in enumerate(models):
            capabilities = model.capabilities
            if not capabilities.verified:
                capability_label = "Não verificado"
            else:
                labels = []
                if capabilities.chat:
                    labels.append("Chat")
                if capabilities.embeddings:
                    labels.append("Embeddings")
                if capabilities.vision:
                    labels.append("Visão")
                if capabilities.tool_calling:
                    labels.append("Tools")
                capability_label = " + ".join(labels) or "Outras"

            self.table.setItem(row, 0, QTableWidgetItem(model.name))
            self.table.setItem(row, 1, QTableWidgetItem(capability_label))
            self.table.setItem(row, 2, QTableWidgetItem(format_size(model.size_bytes)))
            self.table.setItem(row, 3, QTableWidgetItem(model.digest or "—"))
        if healthy:
            self.status_label.setText(f"Ollama conectado — {len(models)} modelo(s) instalado(s).")
        else:
            self.status_label.setText("Ollama indisponível. Verifique o endereço e o serviço.")
