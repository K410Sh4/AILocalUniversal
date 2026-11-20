"""Interface de chat e navegação de conversas."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def markdown_to_html(markdown_text: str) -> str:
    """Renderiza Markdown GitHub, descartando HTML fornecido no próprio texto."""
    document = QTextDocument()
    features = (
        QTextDocument.MarkdownFeature.MarkdownDialectGitHub
        | QTextDocument.MarkdownFeature.MarkdownNoHTML
    )
    document.setMarkdown(markdown_text, features)
    html = document.toHtml()
    body_start = html.find("<body")
    if body_start < 0:
        return html
    content_start = html.find(">", body_start)
    content_end = html.rfind("</body>")
    if content_start < 0 or content_end < content_start:
        return html
    return html[content_start + 1 : content_end]


def build_transcript_html(messages: list[dict[str, str]]) -> str:
    """Monta balões de conversa com contraste, espaçamento e tipografia consistentes."""
    pieces = [
        "<html><head><meta charset=\"utf-8\"><style>"
        "body{font-family:'Noto Sans',sans-serif;font-size:10pt;color:#e8edf4;}"
        "p{margin-top:3px;margin-bottom:9px;}"
        "p:last-child{margin-bottom:0;}"
        "ul,ol{margin-top:4px;margin-bottom:9px;}"
        "li{margin-bottom:4px;}"
        "h1{font-size:17pt;margin-top:8px;margin-bottom:10px;}"
        "h2{font-size:14pt;margin-top:8px;margin-bottom:8px;}"
        "h3{font-size:12pt;margin-top:7px;margin-bottom:7px;}"
        "pre{white-space:pre-wrap;word-wrap:break-word;"
        "font-family:monospace;font-size:9pt;background-color:#151a20;"
        "color:#e6edf3;padding:10px;}"
        "code{font-family:monospace;font-size:9pt;color:#e6edf3;"
        "background-color:#171e26;}"
        "pre code{background-color:transparent;}"
        "a{color:#8ecbff;text-decoration:none;}"
        "table{border-collapse:collapse;}"
        "th,td{border:1px solid #46515e;padding:5px 8px;}"
        "blockquote{color:#cbd5e1;}"
        "*{text-decoration:none;}"
        "</style></head><body>"
    ]
    for message in messages:
        role = message.get("role", "assistant")
        if role not in {"user", "assistant"}:
            continue
        is_user = role == "user"
        label = "Você" if is_user else "AILocal"
        width = "86%" if is_user else "96%"
        alignment = "right" if is_user else "left"
        background = "#203b53" if is_user else "#252b33"
        label_color = "#c6e2fa" if is_user else "#b9cce0"
        content = markdown_to_html(message.get("content", ""))
        pieces.append(
            f'<table width="{width}" align="{alignment}" border="0" '
            f'cellspacing="0" cellpadding="12">'
            f'<tr><td bgcolor="{background}">'
            f'<font color="{label_color}"><b>{label}</b></font><br/>'
            f'<div>{content}</div>'
            "</td></tr></table><br/>"
        )
    pieces.append("</body></html>")
    return "".join(pieces)


class ChatView(QWidget):
    send_requested = Signal(str)
    cancel_requested = Signal()
    refresh_models_requested = Signal()
    settings_requested = Signal()
    new_conversation_requested = Signal()
    conversation_selected = Signal(str)
    mode_changed = Signal(str)
    model_changed = Signal(str)
    preferred_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.mode_combo.currentIndexChanged.connect(self._emit_mode)
        self.model_combo.currentTextChanged.connect(self.model_changed.emit)
        self.send_button.clicked.connect(self._send)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.refresh_button.clicked.connect(self.refresh_models_requested.emit)
        self.settings_button.clicked.connect(self.settings_requested.emit)
        self.new_button.clicked.connect(self.new_conversation_requested.emit)
        self.preferred_button.clicked.connect(self.preferred_requested.emit)
        self.history_list.currentItemChanged.connect(self._conversation_changed)

    def _build_ui(self) -> None:
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Automático", "auto")
        self.mode_combo.addItem("Manual", "manual")
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(180)
        self.preferred_button = QPushButton("Definir preferido")
        self.refresh_button = QPushButton("Atualizar modelos")
        self.settings_button = QPushButton("Configurações")

        top = QHBoxLayout()
        top.addWidget(QLabel("Seleção:"))
        top.addWidget(self.mode_combo)
        top.addWidget(QLabel("Modelo / preferência:"))
        top.addWidget(self.model_combo, 1)
        top.addWidget(self.preferred_button)
        top.addWidget(self.refresh_button)
        top.addWidget(self.settings_button)

        self.history_list = QListWidget()
        self.history_list.setMinimumWidth(190)
        self.new_button = QPushButton("＋ Nova conversa")
        history_panel = QWidget()
        history_layout = QVBoxLayout(history_panel)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.addWidget(self.new_button)
        history_layout.addWidget(self.history_list)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        self.transcript.setOpenLinks(False)
        self.transcript.setStyleSheet(
            "QTextBrowser { padding: 8px; border: 1px solid palette(mid); "
            "border-radius: 8px; background-color: #111418; }"
        )
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("Escreva sua mensagem…")
        self.input_edit.setMaximumBlockCount(10000)
        self.input_edit.setFixedHeight(105)

        self.status_label = QLabel("Desconectado")
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.send_button = QPushButton("Enviar")
        self.send_button.setDefault(True)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)

        input_buttons = QHBoxLayout()
        input_buttons.addWidget(self.status_label, 1)
        input_buttons.addWidget(self.cancel_button)
        input_buttons.addWidget(self.send_button)

        chat_panel = QWidget()
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.addWidget(self.transcript, 1)
        chat_layout.addWidget(self.input_edit)
        chat_layout.addLayout(input_buttons)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(history_panel)
        splitter.addWidget(chat_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 850])

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)

    def _emit_mode(self, _index: int) -> None:
        self.preferred_button.setEnabled(self.mode_combo.currentData() == "auto")
        self.mode_changed.emit(str(self.mode_combo.currentData()))

    def _send(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if text:
            self.input_edit.clear()
            self.send_requested.emit(text)

    def _conversation_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is not None:
            self.conversation_selected.emit(str(current.data(Qt.ItemDataRole.UserRole)))

    def set_mode(self, mode: str) -> None:
        index = self.mode_combo.findData(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)

    def set_models(self, models: list[str], selected: str | None = None) -> None:
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if selected:
            index = self.model_combo.findText(selected)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)
        self.preferred_button.setEnabled(self.mode_combo.currentData() == "auto")

    def set_history(self, conversations: list[tuple[str, str]], selected_id: str | None) -> None:
        self.history_list.blockSignals(True)
        self.history_list.clear()
        selected_item = None
        for conversation_id, title in conversations:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, conversation_id)
            self.history_list.addItem(item)
            if conversation_id == selected_id:
                selected_item = item
        if selected_item is not None:
            self.history_list.setCurrentItem(selected_item)
        self.history_list.blockSignals(False)

    def render_messages(self, messages: list[dict[str, str]]) -> None:
        self.transcript.setHtml(build_transcript_html(messages))
        scrollbar = self.transcript.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def set_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.input_edit.setReadOnly(busy)
        self.history_list.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.settings_button.setEnabled(not busy)
        self.new_button.setEnabled(not busy)
        self.mode_combo.setEnabled(not busy)
        self.model_combo.setEnabled(not busy)
        self.preferred_button.setEnabled(not busy and self.mode_combo.currentData() == "auto")
