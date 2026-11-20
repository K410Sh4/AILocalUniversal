"""Ponto de entrada da aplicação desktop."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    """Cria e executa a aplicação Qt."""
    application = QApplication(sys.argv)
    application.setApplicationName("AILocal Universal")
    application.setOrganizationName("AILocal")
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
