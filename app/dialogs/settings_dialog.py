"""Diálogo de configuração do backend local."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QComboBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from storage.configuration import AppConfig, ConfigurationError


class SettingsDialog(QDialog):
    """Edita URL, keep-alive e system prompt."""

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(560)
        self._original = config

        self.url_edit = QLineEdit(config.base_url)
        self.keep_alive_edit = QLineEdit(config.keep_alive)
        self.prompt_edit = QPlainTextEdit(config.system_prompt)
        self.prompt_edit.setMinimumHeight(130)
        self.resource_profile_combo = QComboBox()
        self.resource_profile_combo.addItem("Leve — 33%", "light")
        self.resource_profile_combo.addItem("Médio — 66%", "medium")
        self.resource_profile_combo.addItem("Ultra — 95%", "ultra")
        selected_profile = self.resource_profile_combo.findData(config.resource_profile)
        if selected_profile >= 0:
            self.resource_profile_combo.setCurrentIndex(selected_profile)

        form = QFormLayout()
        form.addRow("URL do Ollama", self.url_edit)
        form.addRow("Keep alive", self.keep_alive_edit)
        form.addRow("System prompt", self.prompt_edit)
        form.addRow("Orçamento de processamento", self.resource_profile_combo)
        profile_hint = QLabel(
            "Os perfis ajustam o limite aproximado de threads de CPU enviado ao Ollama. "
            "A ocupação real da CPU e o uso da GPU dependem do runtime e da carga."
        )
        profile_hint.setWordWrap(True)
        form.addRow("", profile_hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.config: AppConfig | None = None

    def _accept(self) -> None:
        candidate = AppConfig(
            base_url=self.url_edit.text().strip(),
            mode=self._original.mode,
            preferred_model=self._original.preferred_model,
            manual_model=self._original.manual_model,
            system_prompt=self.prompt_edit.toPlainText().strip(),
            keep_alive=self.keep_alive_edit.text().strip(),
            embedding_model=self._original.embedding_model,
            knowledge_enabled=self._original.knowledge_enabled,
            resource_profile=str(self.resource_profile_combo.currentData()),
        )
        try:
            candidate.validate()
        except ConfigurationError as exc:
            QMessageBox.warning(self, "Configuração inválida", str(exc))
            return
        self.config = candidate
        self.accept()
