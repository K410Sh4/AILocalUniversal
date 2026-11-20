"""Interface de chat e navegação de conversas."""

from __future__ import annotations

import re
from html import escape

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


_MATH_PATTERN = re.compile(
    r"(?P<display_dollar>\$\$(?P<display_dollar_body>.+?)\$\$)"
    r"|(?P<display_bracket>\\\[(?P<display_bracket_body>.*?)\\\])"
    r"|(?P<inline_dollar>(?<!\\)\$(?!\$)(?P<inline_dollar_body>[^\n$]+?)(?<!\\)\$(?!\$))"
    r"|(?P<inline_paren>\\\((?P<inline_paren_body>.*?)\\\))",
    re.DOTALL,
)
_CODE_PATTERN = re.compile(
    r"(?ms)^(\x60{3}|~~~)[^\n]*\n.*?^\1\s*$|(?<!\x60)\x60[^\x60\n]+\x60(?!\x60)"
)
_TEX_SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "theta": "θ", "lambda": "λ", "mu": "μ",
    "sigma": "σ", "omega": "ω", "Delta": "Δ", "Gamma": "Γ",
    "Lambda": "Λ", "Omega": "Ω", "pi": "π", "infty": "∞",
    "int": "∫", "iint": "∬", "oint": "∮", "sum": "∑", "prod": "∏",
    "cdot": "·", "times": "×", "div": "÷", "pm": "±", "mp": "∓",
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "neq": "≠",
    "approx": "≈", "equiv": "≡", "to": "→", "rightarrow": "→",
    "leftarrow": "←", "in": "∈", "notin": "∉", "subset": "⊂",
    "supset": "⊃", "cup": "∪", "cap": "∩", "partial": "∂",
    "nabla": "∇", "therefore": "∴", "degree": "°", "ell": "ℓ",
}
_TEX_FORMAT_COMMANDS = {"text", "mathrm", "mathbf", "mathit", "operatorname"}


def _read_tex_group(source: str, start: int) -> tuple[str, int]:
    """Lê um grupo entre chaves, respeitando grupos aninhados."""
    if start >= len(source):
        return "", start
    if source[start] != "{":
        return source[start], start + 1

    depth = 1
    index = start + 1
    while index < len(source) and depth:
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
        index += 1
    return source[start + 1 : index - 1], index


def _render_tex(source: str) -> str:
    """Converte um subconjunto comum de LaTeX em HTML seguro e suportado pelo Qt."""
    output: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]

        if char == "\\":
            if index + 1 >= len(source):
                output.append("\\")
                break
            if source[index + 1] in "{}_%#$":
                output.append(escape(source[index + 1]))
                index += 2
                continue

            end = index + 1
            while end < len(source) and source[end].isalpha():
                end += 1
            command = source[index + 1 : end]
            if not command:
                output.append(" ")
                index += 2
                continue

            cursor = end
            while cursor < len(source) and source[cursor].isspace():
                cursor += 1

            if command in {"frac", "dfrac", "tfrac"}:
                numerator, after_num = _read_tex_group(source, cursor)
                while after_num < len(source) and source[after_num].isspace():
                    after_num += 1
                denominator, after_den = _read_tex_group(source, after_num)
                if after_num == cursor or after_den == after_num:
                    output.append(escape("\\" + command))
                    index = end
                    continue
                output.append(
                    '<span class="math-frac"><sup>'
                    + _render_tex(numerator)
                    + '</sup><span class="math-frac-slash">⁄</span><sub>'
                    + _render_tex(denominator)
                    + "</sub></span>"
                )
                index = after_den
                continue

            if command == "sqrt":
                radicand, after = _read_tex_group(source, cursor)
                if after == cursor:
                    output.append("√")
                    index = end
                else:
                    output.append('√<span class="math-radicand">(')
                    output.append(_render_tex(radicand))
                    output.append(")</span>")
                    index = after
                continue

            if command in _TEX_FORMAT_COMMANDS:
                argument, after = _read_tex_group(source, cursor)
                if after == cursor:
                    output.append(escape("\\" + command))
                    index = end
                else:
                    output.append('<span class="math-text">')
                    output.append(_render_tex(argument))
                    output.append("</span>")
                    index = after
                continue

            if command in {"left", "right", "displaystyle", "textstyle"}:
                index = end
                continue
            if command in {"quad", "qquad", "enspace"}:
                output.append("&nbsp;&nbsp;" if command != "qquad" else "&nbsp;&nbsp;&nbsp;&nbsp;")
                index = end
                continue
            output.append(escape(_TEX_SYMBOLS.get(command, "\\" + command)))
            index = end
            continue

        if char in {"^", "_"}:
            value, after = _read_tex_group(source, index + 1)
            tag = "sup" if char == "^" else "sub"
            output.append(f"<{tag}>{_render_tex(value)}</{tag}>")
            index = after
            continue

        if char == "{":
            group, after = _read_tex_group(source, index)
            output.append(_render_tex(group))
            index = after
            continue
        if char == "}":
            index += 1
            continue
        output.append(escape(char))
        index += 1

    return "".join(output)


def _replace_math(markdown_text: str) -> tuple[str, dict[str, str]]:
    """Substitui fórmulas fora de trechos de código por marcadores opacos."""
    code_ranges = [(match.start(), match.end()) for match in _CODE_PATTERN.finditer(markdown_text)]
    replacements: dict[str, str] = {}
    parts: list[str] = []
    cursor = 0

    for match in _MATH_PATTERN.finditer(markdown_text):
        if any(start <= match.start() < end for start, end in code_ranges):
            continue

        display_group = next(
            (
                name
                for name in ("display_dollar_body", "display_bracket_body")
                if match.group(name) is not None
            ),
            None,
        )
        inline_group = next(
            (
                name
                for name in ("inline_dollar_body", "inline_paren_body")
                if match.group(name) is not None
            ),
            None,
        )
        group = display_group or inline_group
        if group is None:
            continue

        parts.append(markdown_text[cursor : match.start()])
        token = f"AILUMATHPLACEHOLDER{len(replacements):05d}X"
        expression = _render_tex(match.group(group).strip())
        css_class = "math-display" if display_group else "math-inline"
        replacements[token] = f'<span class="{css_class}">{expression}</span>'
        parts.append(token)
        cursor = match.end()

    parts.append(markdown_text[cursor:])
    return "".join(parts), replacements


def markdown_to_html(markdown_text: str) -> str:
    """Renderiza Markdown e um subconjunto seguro de notação matemática LaTeX."""
    prepared_markdown, math_replacements = _replace_math(markdown_text)
    document = QTextDocument()
    document.setIndentWidth(46.0)
    document.setDefaultStyleSheet(
        "p { margin-top: 3px; margin-bottom: 8px; }"
        "ul, ol { margin-top: 6px; margin-bottom: 11px; }"
        "li { margin-top: 3px; margin-bottom: 5px; }"
    )
    features = (
        QTextDocument.MarkdownFeature.MarkdownDialectGitHub
        | QTextDocument.MarkdownFeature.MarkdownNoHTML
    )
    document.setMarkdown(prepared_markdown, features)
    html = document.toHtml()
    body_start = html.find("<body")
    if body_start < 0:
        result = html
    else:
        content_start = html.find(">", body_start)
        content_end = html.rfind("</body>")
        if content_start < 0 or content_end < content_start:
            result = html
        else:
            result = html[content_start + 1 : content_end]

    for token, rendered_math in math_replacements.items():
        result = result.replace(token, rendered_math)
    return result


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
        ".math-inline{font-family:'Noto Serif',serif;font-size:1.08em;color:#f1f5f9;"
        "white-space:nowrap;}"
        ".math-display{display:block;text-align:center;padding:5px 12px;"
        "margin:4px 2px;background-color:#1b222b;border-radius:5px;"
        "font-family:'Noto Serif',serif;font-size:1.12em;color:#f1f5f9;}"
        ".math-frac{white-space:nowrap;}"
        ".math-frac sup,.math-frac sub{font-size:.78em;}"
        ".math-frac-slash{padding:0 1px;}"
        ".math-radicand{padding-left:2px;}"
        ".math-text{font-family:'Noto Sans',sans-serif;font-size:.94em;}"
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
