"""Janela inicial mínima; views funcionais serão adicionadas por fase."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    """Janela principal do AILocal Universal."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AILocal Universal")
        self.resize(1100, 720)
        tabs = QTabWidget()
        tabs.addTab(self._page("Fundação do projeto: documentação, contratos e estrutura inicial."), "Visão geral")
        tabs.addTab(self._page("Integração de modelos prevista para a Fase 1."), "Modelos")
        tabs.addTab(self._page("Chat será integrado ao Engine Adapter na Fase 1."), "Chat")
        self.setCentralWidget(tabs)

    @staticmethod
    def _page(message: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        return page
