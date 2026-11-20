"""Interface de ingestão e consulta da biblioteca de conhecimento local."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from knowledge.library import default_knowledge_directory
from workers.knowledge_workers import KnowledgeLibraryWorker


class KnowledgeView(QWidget):
    """Gerencia arquivos e pesquisa local; não injeta resultados no Chat."""

    embedding_model_changed = Signal(str)

    def __init__(
        self,
        *,
        ollama_url: str,
        embedding_model: str | None = None,
        data_directory: str | Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.ollama_url = ollama_url
        self.data_directory = (
            Path(data_directory) if data_directory is not None else default_knowledge_directory()
        )
        self._worker: KnowledgeLibraryWorker | None = None
        self._pending_operation: str | None = None
        self._build_ui()
        self.set_embedding_models([], embedding_model)
        self.refresh_documents()

    @property
    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _build_ui(self) -> None:
        self.title_label = QLabel("Conhecimento local")
        self.title_label.setStyleSheet("font-size: 16pt; font-weight: 600;")
        self.description_label = QLabel(
            "Adicione documentos à biblioteca local. O conteúdo não será enviado ao Chat "
            "automaticamente; esta aba permite gerenciar e testar a recuperação."
        )
        self.description_label.setWordWrap(True)

        self.embedding_combo = QComboBox()
        self.embedding_combo.setMinimumWidth(220)
        self.embedding_combo.setToolTip(
            "Modelo usado somente para gerar embeddings dos documentos e das consultas."
        )
        self.embedding_combo.currentIndexChanged.connect(self._embedding_selection_changed)
        self.embedding_status = QLabel("Busca lexical")
        self.embedding_status.setWordWrap(True)

        self.add_button = QPushButton("Adicionar documentos…")
        self.remove_button = QPushButton("Remover selecionado")
        self.refresh_button = QPushButton("Atualizar lista")
        self.reindex_button = QPushButton("Reindexar vetores")
        self.add_button.clicked.connect(self._choose_files)
        self.remove_button.clicked.connect(self._remove_selected)
        self.refresh_button.clicked.connect(self.refresh_documents)
        self.reindex_button.clicked.connect(self._reindex_vectors)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Modelo de embeddings:"))
        controls.addWidget(self.embedding_combo, 1)
        controls.addWidget(self.embedding_status, 1)
        controls.addWidget(self.add_button)
        controls.addWidget(self.remove_button)
        controls.addWidget(self.reindex_button)
        controls.addWidget(self.refresh_button)

        self.documents_table = QTableWidget(0, 5)
        self.documents_table.setHorizontalHeaderLabels(
            ["Documento", "Formato", "Trechos", "Tamanho", "Origem"]
        )
        self.documents_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.documents_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.documents_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.documents_table.verticalHeader().setVisible(False)
        self.documents_table.horizontalHeader().setStretchLastSection(True)
        self.documents_table.setColumnWidth(0, 220)
        self.documents_table.setColumnWidth(1, 130)
        self.documents_table.setColumnWidth(2, 80)
        self.documents_table.setColumnWidth(3, 100)

        self.search_edit = QPlainTextEdit()
        self.search_edit.setPlaceholderText("Digite uma consulta para testar a recuperação local…")
        self.search_edit.setFixedHeight(76)
        self.search_button = QPushButton("Testar busca")
        self.search_button.clicked.connect(self._search)

        search_controls = QHBoxLayout()
        search_controls.addWidget(QLabel("Prévia de recuperação:"))
        search_controls.addStretch(1)
        search_controls.addWidget(self.search_button)

        self.results_text = QPlainTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText(
            "Os trechos recuperados e suas citações aparecerão aqui."
        )
        self.results_text.setMinimumHeight(180)

        self.status_label = QLabel(
            f"Biblioteca local: {self.data_directory}"
        )
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addLayout(controls)
        layout.addWidget(self.documents_table, 1)
        layout.addLayout(search_controls)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.results_text, 1)
        layout.addWidget(self.status_label)

    def set_base_url(self, url: str) -> None:
        self.ollama_url = url.rstrip("/")

    def set_embedding_models(
        self,
        model_names: list[str],
        selected: str | None = None,
    ) -> None:
        selected_value = selected if selected is not None else str(
            self.embedding_combo.currentData() or ""
        )
        names = list(dict.fromkeys(name for name in model_names if name))
        self.embedding_combo.blockSignals(True)
        self.embedding_combo.clear()
        self.embedding_combo.addItem("Somente busca lexical", "")
        for name in names:
            self.embedding_combo.addItem(name, name)
        if selected_value and selected_value not in names:
            self.embedding_combo.addItem(f"{selected_value} (não detectado)", selected_value)
        target_index = self.embedding_combo.findData(selected_value or "")
        self.embedding_combo.setCurrentIndex(max(0, target_index))
        self.embedding_combo.blockSignals(False)
        self._update_embedding_status()
        self.reindex_button.setEnabled(bool(selected_value))

    def _embedding_selection_changed(self, _index: int) -> None:
        value = str(self.embedding_combo.currentData() or "")
        self._update_embedding_status()
        self.reindex_button.setEnabled(bool(value) and not self.is_busy)
        self.embedding_model_changed.emit(value)

    def _update_embedding_status(self) -> None:
        model = str(self.embedding_combo.currentData() or "")
        if model and self.embedding_combo.currentText().endswith("(não detectado)"):
            self.embedding_status.setText(
                f"Modelo {model} não foi detectado pelo Ollama atual. "
                "Atualize os modelos ou escolha outro antes de indexar."
            )
        elif model:
            self.embedding_status.setText(
                f"Embeddings: {model}. Arquivos novos serão indexados lexical e vetorialmente."
            )
        else:
            self.embedding_status.setText(
                "Busca lexical. Selecione um modelo para ativar a indexação vetorial."
            )

    def _start_worker(
        self,
        operation: str,
        *,
        file_paths: tuple[str, ...] = (),
        document_ids: tuple[str, ...] = (),
        query: str = "",
    ) -> None:
        if self.is_busy:
            return
        worker = KnowledgeLibraryWorker(
            operation,
            data_directory=self.data_directory,
            ollama_url=self.ollama_url,
            embedding_model=str(self.embedding_combo.currentData() or "") or None,
            file_paths=file_paths,
            document_ids=document_ids,
            query=query,
            parent=self,
        )
        self._worker = worker
        self._pending_operation = operation
        worker.progress.connect(self.status_label.setText)
        worker.completed.connect(self._on_worker_completed)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(lambda w=worker: self._worker_finished(w))
        self._set_busy(True)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        for control in (
            self.add_button,
            self.remove_button,
            self.refresh_button,
            self.search_button,
            self.embedding_combo,
        ):
            control.setEnabled(not busy)
        self.reindex_button.setEnabled(
            not busy and bool(self.embedding_combo.currentData())
        )
        self.documents_table.setEnabled(not busy)
        self.search_edit.setReadOnly(busy)

    def _worker_finished(self, worker: KnowledgeLibraryWorker) -> None:
        if self._worker is worker:
            self._worker = None
            self._pending_operation = None
            self._set_busy(False)
        worker.deleteLater()

    def _on_worker_completed(self, payload: object) -> None:
        if not isinstance(payload, dict):
            self.status_label.setText("A biblioteca retornou uma resposta inválida.")
            return
        operation = payload.get("operation")
        if operation in {"list", "ingest", "delete", "reindex"}:
            self._populate_documents(payload.get("documents", []))
        if operation == "ingest":
            result = payload.get("result", {})
            items = result.get("items", []) if isinstance(result, dict) else []
            messages = []
            for item in items:
                if item.get("status") == "failed":
                    messages.append(f"Falha: {item.get('title')}: {item.get('error')}")
                elif item.get("vector_warning"):
                    messages.append(
                        f"Indexado lexicalmente; embeddings falharam para "
                        f"{item.get('title')}: {item['vector_warning']}"
                    )
                else:
                    messages.append(
                        f"{item.get('title')}: {item.get('chunk_count')} trecho(s), "
                        f"{item.get('vector_count')} vetor(es)."
                    )
            self.status_label.setText("\n".join(messages) or "Nenhum documento processado.")
        elif operation == "reindex":
            result = payload.get("result", {})
            self.status_label.setText(
                f"Reindexação vetorial concluída: {result.get('indexed_documents', 0)} "
                f"documento(s), {result.get('vector_count', 0)} vetor(es); "
                f"falhas: {result.get('failed_documents', 0)}."
            )
        elif operation == "delete":
            result = payload.get("result", {})
            self.status_label.setText(
                f"Documentos removidos: {result.get('deleted', 0)}."
            )
        elif operation == "search":
            citations = payload.get("citations", [])
            text = str(payload.get("text", ""))
            self.results_text.setPlainText(
                text or "Nenhum trecho recuperado para esta consulta."
            )
            warning = str(payload.get("warning") or "")
            suffix = f" Aviso: {warning}" if warning else ""
            self.status_label.setText(
                f"Prévia concluída — {len(citations)} fonte(s), "
                f"{payload.get('char_count', 0)} caracteres.{suffix}"
            )

    def _on_worker_failed(self, message: str) -> None:
        self.status_label.setText(f"Falha na biblioteca: {message}")

    def _populate_documents(self, documents: object) -> None:
        rows = documents if isinstance(documents, list) else []
        self.documents_table.setRowCount(len(rows))
        for row, document in enumerate(rows):
            if not isinstance(document, dict):
                continue
            source_uri = str(document.get("source_uri", ""))
            title = str(document.get("title", Path(source_uri).name or "Documento"))
            media_type = str(document.get("media_type", ""))
            size = int(document.get("size_bytes", 0))
            values = [
                title,
                media_type,
                str(document.get("chunk_count", 0)),
                self._format_size(size),
                source_uri,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, str(document.get("document_id", "")))
                self.documents_table.setItem(row, column, item)
        self.documents_table.resizeRowsToContents()
        self.status_label.setText(
            f"{len(rows)} documento(s) indexado(s) • {self.data_directory}"
        )

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(max(0, size))
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}"
            value /= 1024
        return "—"

    def refresh_documents(self) -> None:
        self._start_worker("list")

    def _choose_files(self) -> None:
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Adicionar documentos à biblioteca local",
            str(Path.home()),
            "Documentos suportados (*.txt *.text *.log *.csv *.json *.yaml *.yml "
            "*.toml *.py *.sh *.ini *.cfg *.xml *.sql *.md *.markdown *.pdf);;"
            "Todos os arquivos (*)",
        )
        if files:
            self._start_worker("ingest", file_paths=tuple(files))

    def _remove_selected(self) -> None:
        row = self.documents_table.currentRow()
        if row < 0:
            self.status_label.setText("Selecione um documento para remover.")
            return
        item = self.documents_table.item(row, 0)
        document_id = str(item.data(Qt.ItemDataRole.UserRole)) if item else ""
        if not document_id:
            return
        answer = QMessageBox.question(
            self,
            "Remover documento",
            "Remover o texto extraído e os vetores deste documento do índice local?\n"
            "O arquivo original não será apagado.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start_worker("delete", document_ids=(document_id,))

    def _reindex_vectors(self) -> None:
        if not self.embedding_combo.currentData():
            self.status_label.setText("Selecione um modelo de embeddings antes de reindexar.")
            return
        self._start_worker("reindex")

    def _search(self) -> None:
        query = self.search_edit.toPlainText().strip()
        if query:
            self._start_worker("search", query=query)
