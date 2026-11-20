"""Painel de inspeção da análise e do plano cognitivo mais recente."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.cognitive_inspector import build_inspector_snapshot
from core.cognitive_task import CognitiveTask


def _display(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


class CognitiveInspectorView(QWidget):
    """Mostra a última tarefa analisada nesta sessão, sem inferir dados ausentes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._snapshot: dict[str, Any] | None = None
        self._metric_bars: dict[str, QProgressBar] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.title_label = QLabel("Cognitive Inspector — última tarefa desta sessão")
        self.title_label.setStyleSheet("font-size: 16pt; font-weight: 600;")
        self.runtime_label = QLabel("Nenhuma tarefa analisada nesta sessão.")
        self.runtime_label.setWordWrap(True)
        self.task_label = QLabel("Task ID: —")
        self.task_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        summary = QGroupBox("Resumo da tarefa")
        summary_form = QFormLayout(summary)
        self.intent_label = QLabel("—")
        self.route_label = QLabel("—")
        self.status_label = QLabel("—")
        self.model_label = QLabel("—")
        for label in (
            self.intent_label,
            self.route_label,
            self.status_label,
            self.model_label,
        ):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary_form.addRow("Intenção:", self.intent_label)
        summary_form.addRow("Rota planejada:", self.route_label)
        summary_form.addRow("Estado da análise:", self.status_label)
        summary_form.addRow("Modelo selecionado:", self.model_label)

        inputs = QGroupBox("Entrada")
        inputs_layout = QVBoxLayout(inputs)
        self.original_text = QPlainTextEdit()
        self.original_text.setReadOnly(True)
        self.original_text.setPlaceholderText("O texto original aparecerá aqui.")
        self.original_text.setMaximumHeight(82)
        self.normalized_text = QPlainTextEdit()
        self.normalized_text.setReadOnly(True)
        self.normalized_text.setPlaceholderText("A forma normalizada aparecerá aqui.")
        self.normalized_text.setMaximumHeight(82)
        inputs_layout.addWidget(QLabel("Texto original"))
        inputs_layout.addWidget(self.original_text)
        inputs_layout.addWidget(QLabel("Texto normalizado"))
        inputs_layout.addWidget(self.normalized_text)

        metrics = QGroupBox(
            "Indicadores heurísticos — não representam probabilidades"
        )
        metrics_form = QFormLayout(metrics)
        for key, title in (
            ("difficulty", "Dificuldade"),
            ("uncertainty", "Incerteza"),
            ("risk", "Risco"),
            ("urgency", "Urgência"),
        ):
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFormat("Não calculado")
            bar.setTextVisible(True)
            bar.setToolTip(
                "Estimativa heurística do pipeline. Não é uma probabilidade calibrada."
            )
            self._metric_bars[key] = bar
            metrics_form.addRow(title + ":", bar)

        capabilities = QGroupBox(
            "Afinidade lexical por capacidade — escala indicativa de 0 a 1"
        )
        capabilities_layout = QVBoxLayout(capabilities)
        self.capabilities_table = QTableWidget(0, 2)
        self.capabilities_table.setHorizontalHeaderLabels(["Dimensão", "Afinidade"])
        self.capabilities_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.capabilities_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.capabilities_table.verticalHeader().setVisible(False)
        self.capabilities_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.capabilities_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.capabilities_table.setMaximumHeight(390)
        capabilities_layout.addWidget(self.capabilities_table)

        self.subtasks_table = self._create_table(
            ["#", "Subtarefa", "Intenção", "Dependências", "Estado", "Execução", "Verificação", "Resultado"]
        )
        self.plan_table = self._create_table(
            ["Etapa", "Componente", "Estratégia / detalhe"]
        )
        self.trace_table = self._create_table(
            ["Horário", "Estágio", "Evento", "Detalhes"]
        )
        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(90)
        self.result_text.setPlaceholderText("Nenhum resultado determinístico registrado.")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.addWidget(self.title_label)
        layout.addWidget(self.task_label)
        layout.addWidget(self.runtime_label)
        layout.addWidget(summary)
        layout.addWidget(inputs)
        layout.addWidget(metrics)
        layout.addWidget(capabilities)
        layout.addWidget(self._group_table("Subtarefas e dependências", self.subtasks_table))
        layout.addWidget(self._group_table("Plano de execução", self.plan_table))
        layout.addWidget(self._group_table("Execution Trace", self.trace_table))
        result_group = QGroupBox("Resultado da execução")
        result_layout = QVBoxLayout(result_group)
        result_layout.addWidget(self.result_text)
        layout.addWidget(result_group)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        root = QVBoxLayout(self)
        root.addWidget(scroll)

    @staticmethod
    def _create_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        if len(headers) > 1:
            table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch
            )
        for column in range(2, len(headers)):
            table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        table.setWordWrap(True)
        table.setMinimumHeight(90)
        return table

    @staticmethod
    def _group_table(title: str, table: QTableWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(table)
        return group

    @staticmethod
    def _populate_table(
        table: QTableWidget,
        rows: list[list[str]],
    ) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                table.setItem(row_index, column_index, item)
        table.resizeRowsToContents()
        content_height = (
            table.horizontalHeader().sizeHint().height()
            + sum(table.rowHeight(row) for row in range(table.rowCount()))
            + 2 * table.frameWidth()
        )
        target_height = max(90, min(380, content_height))
        table.setMinimumHeight(target_height)
        table.setMaximumHeight(target_height)

    def set_task(self, task: CognitiveTask | None) -> None:
        if task is None:
            self.clear()
            return
        snapshot = build_inspector_snapshot(task)
        self._snapshot = snapshot
        self.task_label.setText(
            f"Task ID: {snapshot['task_id']}  •  schema {snapshot['schema_version']}"
        )
        self.intent_label.setText(snapshot["intent"])
        self.route_label.setText(snapshot["route"])
        self.status_label.setText(snapshot["status"])
        self.model_label.setText(_display(snapshot["selected_model"]))
        self.original_text.setPlainText(snapshot["original_text"])
        self.normalized_text.setPlainText(snapshot["normalized_text"])

        for key, bar in self._metric_bars.items():
            value = snapshot["metrics"][key]
            if value is None:
                bar.setValue(0)
                bar.setFormat("Não calculado")
            else:
                bar.setValue(round(float(value) * 100))
                bar.setFormat(f"{float(value):.3f}  (indicador heurístico)")

        capability_rows = [
            [item["dimension"], f"{item['score']:.3f}"]
            for item in snapshot["capabilities"]
        ]
        self._populate_table(self.capabilities_table, capability_rows)

        subtask_rows = []
        for item in snapshot["subtasks"]:
            dependencies = ", ".join(
                str(value).rsplit(":", 1)[-1] for value in item.get("depends_on", [])
            ) or "Nenhuma"
            result = item.get("result", {})
            result_content = str(result.get("content", "")) if isinstance(result, dict) else ""
            execution_kind = str(item.get("execution_kind", "—"))
            execution_label = {
                "deterministic_tool": "Ferramenta local",
                "llm": "Modelo",
            }.get(execution_kind, execution_kind)
            status_label = {
                "pending": "Pendente",
                "running": "Em execução",
                "completed": "Concluída",
                "failed": "Falhou",
                "blocked": "Bloqueada",
                "cancelled": "Cancelada",
                "skipped": "Ignorada",
            }.get(str(item.get("status", "")), str(item.get("status", "—")))
            verification_label = {
                "not_independently_verified": "Não verificada",
                "verified": "Verificada",
            }.get(
                str(item.get("verification_status", "")),
                str(item.get("verification_status", "—")),
            )
            result_summary = (
                result_content.replace("\n", " ")[:140]
                if result_content
                else str(item.get("error", "—"))
            )
            subtask_rows.append(
                [
                    str(item.get("order", "")),
                    str(item.get("text", "")),
                    str(item.get("intent", "—")),
                    dependencies,
                    status_label,
                    execution_label,
                    verification_label,
                    result_summary,
                ]
            )
        self._populate_table(self.subtasks_table, subtask_rows)

        plan_rows = []
        for step in snapshot["execution_plan"]:
            detail = {
                key: value
                for key, value in step.items()
                if key not in {"step", "component"}
            }
            plan_rows.append(
                [
                    str(step.get("step", "")),
                    str(step.get("component", "—")),
                    _display(detail),
                ]
            )
        self._populate_table(self.plan_table, plan_rows)

        trace_rows = []
        for event in snapshot["trace"]:
            details = event.get("details", {})
            trace_rows.append(
                [
                    str(event.get("timestamp", "")),
                    str(event.get("stage", "—")),
                    str(event.get("status", "—")),
                    _display(details),
                ]
            )
        self._populate_table(self.trace_table, trace_rows)

        result = snapshot["result"]
        if result is not None:
            result_lines = []
            for key in ("route", "status", "tool", "model"):
                if result.get(key) is not None:
                    result_lines.append(f"{key}: {result[key]}")
            if result.get("content"):
                result_lines.append(str(result["content"]))
            if result.get("error"):
                result_lines.append(f"Erro: {result['error']}")
            self.result_text.setPlainText("\\n".join(result_lines))
        elif snapshot["deterministic_results"]:
            self.result_text.setPlainText(
                "\\n\\n".join(
                    _display(item) for item in snapshot["deterministic_results"]
                )
            )
        else:
            self.result_text.setPlainText("A execução ainda não produziu um resultado final.")

        if not self.runtime_label.text() or self.runtime_label.text().startswith(
            "Nenhuma tarefa"
        ):
            self.set_runtime_status("Análise cognitiva concluída.")

    def set_runtime_status(self, message: str) -> None:
        self.runtime_label.setText("Execução: " + message)

    def clear(self) -> None:
        self._snapshot = None
        self.task_label.setText("Task ID: —")
        self.intent_label.setText("—")
        self.route_label.setText("—")
        self.status_label.setText("—")
        self.model_label.setText("—")
        self.original_text.clear()
        self.normalized_text.clear()
        for bar in self._metric_bars.values():
            bar.setValue(0)
            bar.setFormat("Não calculado")
        for table in (
            self.capabilities_table,
            self.subtasks_table,
            self.plan_table,
            self.trace_table,
        ):
            table.setRowCount(0)
        self.result_text.clear()
        self.set_runtime_status("Nenhuma tarefa analisada nesta sessão.")
