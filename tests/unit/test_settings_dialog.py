from PySide6.QtWidgets import QApplication

from app.dialogs.settings_dialog import SettingsDialog
from storage.configuration import AppConfig


def test_settings_dialog_preserves_embedding_model_selection() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(
        AppConfig(
            base_url="http://localhost:11434",
            embedding_model="embeddinggemma",
        )
    )

    dialog._accept()

    assert dialog.config is not None
    assert dialog.config.embedding_model == "embeddinggemma"
    dialog.close()
    app.processEvents()
