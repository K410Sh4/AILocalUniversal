"""Diálogo de configuração do backend local e do Adaptive Hardware."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from storage.configuration import AppConfig, ConfigurationError


class SettingsDialog(QDialog):
    """Edita backend, perfil de recursos e política de proteção."""

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(600)
        self._original = config

        self.url_edit = QLineEdit(config.base_url)
        self.keep_alive_edit = QLineEdit(config.keep_alive)
        self.prompt_edit = QPlainTextEdit(config.system_prompt)
        self.prompt_edit.setMinimumHeight(130)

        self.hardware_profile_combo = QComboBox()
        self.hardware_profile_combo.addItem("Automático (recomendado)", "auto")
        self.hardware_profile_combo.addItem("Ultra leve", "ultra_light")
        self.hardware_profile_combo.addItem("Mínimo", "minimal")
        self.hardware_profile_combo.addItem("Equilibrado", "balanced")
        self.hardware_profile_combo.addItem("Desempenho", "performance")
        self.hardware_profile_combo.addItem("Qualidade máxima", "max_quality")
        profile_index = self.hardware_profile_combo.findData(config.hardware_profile)
        self.hardware_profile_combo.setCurrentIndex(max(0, profile_index))

        self.protection_mode_combo = QComboBox()
        self.protection_mode_combo.addItem("Protegido (recomendado)", "protected")
        self.protection_mode_combo.addItem("Adaptativo", "adaptive")
        self.protection_mode_combo.addItem("Permissivo (avançado)", "permissive")
        protection_index = self.protection_mode_combo.findData(config.protection_mode)
        self.protection_mode_combo.setCurrentIndex(max(0, protection_index))

        self.hardware_help = QLabel(
            "Automático escolhe o perfil mais potente que atende aos limites medidos. "
            "O modo protegido bloqueia solicitações incompatíveis; o adaptativo troca "
            "para um perfil inferior elegível. O permissivo não ignora o piso absoluto "
            "de 1,5 GiB de RAM."
        )
        self.hardware_help.setWordWrap(True)

        form = QFormLayout()
        form.addRow("URL do Ollama", self.url_edit)
        form.addRow("Keep alive", self.keep_alive_edit)
        form.addRow("Perfil de hardware", self.hardware_profile_combo)
        form.addRow("Proteção de recursos", self.protection_mode_combo)
        form.addRow("", self.hardware_help)
        form.addRow("System prompt", self.prompt_edit)

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
            hardware_profile=str(self.hardware_profile_combo.currentData()),
            protection_mode=str(self.protection_mode_combo.currentData()),
        )
        try:
            candidate.validate()
        except ConfigurationError as exc:
            QMessageBox.warning(self, "Configuração inválida", str(exc))
            return
        self.config = candidate
        self.accept()
