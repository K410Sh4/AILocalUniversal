"""Janela principal e composição dos serviços da Fase 1."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from app.dialogs.settings_dialog import SettingsDialog
from app.views.chat_view import ChatView
from app.views.models_view import ModelsView
from core.neuralinjector.resources import (
    CompatibilityReport,
    ResourceRequirements,
    detect_hardware,
)
from engines.base import EngineAdapter, EngineRequest, ModelInfo
from engines.model_selector import ModelSelectionError, choose_model
from engines.ollama_engine import OllamaEngine, OllamaResourceProtectionError
from engines.registry import EngineRegistry
from storage.configuration import AppConfig, ConfigurationError, ConfigurationStore
from storage.conversations import Conversation, ConversationStore
from workers.ollama_workers import OllamaChatWorker, OllamaStatusWorker


class MainWindow(QMainWindow):
    """Janela desktop. Operações de rede rodam em QThread workers."""

    def __init__(
        self,
        config_store: ConfigurationStore | None = None,
        conversation_store: ConversationStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AILocal Universal")
        self.resize(1180, 780)

        self.config_store = config_store or ConfigurationStore()
        self.conversation_store = conversation_store or ConversationStore()
        self.config = self._load_config()
        self.engine_registry = EngineRegistry()
        self.engine: EngineAdapter
        self._replace_engine()
        self.models: list[ModelInfo] = []
        self._status_worker: OllamaStatusWorker | None = None
        self._chat_worker: OllamaChatWorker | None = None
        self._current_assistant_index: int | None = None

        self.conversations = self._load_conversations()
        self.conversations.sort(key=lambda item: item.updated_at, reverse=True)
        if self.conversations:
            self.current_conversation = self.conversations[0]
        else:
            self.current_conversation = Conversation()
            self.conversations.append(self.current_conversation)

        self.chat_view = ChatView()
        self.models_view = ModelsView()
        tabs = QTabWidget()
        tabs.addTab(self.chat_view, "Chat")
        tabs.addTab(self.models_view, "Modelos")
        self.setCentralWidget(tabs)

        self.chat_view.send_requested.connect(self.send_message)
        self.chat_view.cancel_requested.connect(self.cancel_generation)
        self.chat_view.refresh_models_requested.connect(self.refresh_backend)
        self.models_view.refresh_requested.connect(self.refresh_backend)
        self.chat_view.settings_requested.connect(self.open_settings)
        self.chat_view.new_conversation_requested.connect(self.new_conversation)
        self.chat_view.conversation_selected.connect(self.select_conversation)
        self.chat_view.mode_changed.connect(self.change_mode)
        self.chat_view.model_changed.connect(self.change_manual_model)
        self.chat_view.preferred_requested.connect(self.set_preferred_model)

        self._refresh_history()
        self._render_current_conversation()
        self.chat_view.set_mode(self.config.mode)
        self.statusBar().showMessage("Pronto")
        self.refresh_backend()

    def _load_config(self) -> AppConfig:
        try:
            return self.config_store.load()
        except ConfigurationError as exc:
            QMessageBox.warning(
                self,
                "Configuração inválida",
                f"Será usada a configuração padrão.\n\n{exc}",
            )
            return AppConfig()

    def _load_conversations(self) -> list[Conversation]:
        try:
            return self.conversation_store.load_all()
        except ValueError as exc:
            QMessageBox.warning(self, "Histórico", str(exc))
            return []

    def _persist_conversations(self) -> None:
        try:
            self.conversation_store.save_all(self.conversations)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Falha ao salvar histórico", str(exc))

    def _refresh_history(self) -> None:
        ordered = sorted(self.conversations, key=lambda item: item.updated_at, reverse=True)
        self.chat_view.set_history(
            [(item.id, item.title) for item in ordered],
            self.current_conversation.id,
        )

    def _render_current_conversation(self) -> None:
        self.chat_view.render_messages(self.current_conversation.messages)

    def _replace_engine(self) -> None:
        if "ollama" in self.engine_registry.names():
            self.engine_registry.unregister("ollama")
        engine = OllamaEngine(self.config.base_url)
        self.engine_registry.register(engine)
        self.engine = self.engine_registry.get("ollama")

    def refresh_backend(self) -> None:
        if self._status_worker is not None and self._status_worker.isRunning():
            return
        self.chat_view.set_status("Consultando Ollama…")
        self.statusBar().showMessage(f"Conectando a {self.config.base_url}")
        worker = OllamaStatusWorker(self.engine, self)
        self._status_worker = worker
        worker.completed.connect(self._on_backend_status)
        worker.failed.connect(self._on_backend_error)
        worker.finished.connect(lambda w=worker: self._status_finished(w))
        worker.start()

    def _status_finished(self, worker: OllamaStatusWorker) -> None:
        if self._status_worker is worker:
            self._status_worker = None
        worker.deleteLater()

    def _on_backend_status(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        healthy = bool(payload.get("healthy"))
        models = payload.get("models", [])
        self.models = models if isinstance(models, list) else []
        names = [model.name for model in self.models]
        selected = (
            self.config.manual_model
            if self.config.mode == "manual"
            else self.config.preferred_model
        )
        self.chat_view.set_models(names, selected)
        self.models_view.set_models(self.models, healthy)
        if healthy:
            message = f"Ollama conectado — {len(self.models)} modelo(s)."
            self.chat_view.set_status(message)
            self.statusBar().showMessage(message)
        else:
            message = "Ollama indisponível. Inicie o serviço e atualize os modelos."
            self.chat_view.set_status(message)
            self.statusBar().showMessage(message)

    def _on_backend_error(self, message: str) -> None:
        self.models = []
        self.chat_view.set_models([])
        self.models_view.set_models([], False)
        self.chat_view.set_status("Erro ao consultar Ollama")
        self.statusBar().showMessage(message, 10000)

    def _save_config(self) -> None:
        try:
            self.config_store.save(self.config)
        except (OSError, ConfigurationError) as exc:
            QMessageBox.warning(self, "Configuração", f"Não foi possível salvar: {exc}")

    def change_mode(self, mode: str) -> None:
        if mode in {"auto", "manual"} and self.config.mode != mode:
            self.config.mode = mode
            self._save_config()

    def change_manual_model(self, model: str) -> None:
        if model and self.config.manual_model != model:
            self.config.manual_model = model
            if self.config.mode == "manual":
                self._save_config()

    def set_preferred_model(self) -> None:
        model = self.chat_view.model_combo.currentText().strip()
        if not model:
            self.statusBar().showMessage("Nenhum modelo disponível para definir como preferido.")
            return
        self.config.preferred_model = model
        self._save_config()
        self.statusBar().showMessage(f"Modelo preferido definido: {model}", 5000)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted and dialog.config:
            previous_url = self.config.base_url
            self.config = dialog.config
            self._save_config()
            if self.config.base_url != previous_url:
                if self._status_worker is not None and self._status_worker.isRunning():
                    self._status_worker.cancel()
                    self._status_worker.wait(1500)
                self._replace_engine()
                self.models = []
                self.chat_view.set_models([])
                self.models_view.set_models([], False)
            self.refresh_backend()

    def new_conversation(self) -> None:
        if self._chat_worker is not None and self._chat_worker.isRunning():
            return
        conversation = Conversation()
        self.conversations.append(conversation)
        self.current_conversation = conversation
        self._persist_conversations()
        self._refresh_history()
        self._render_current_conversation()

    def select_conversation(self, conversation_id: str) -> None:
        if self._chat_worker is not None and self._chat_worker.isRunning():
            return
        for conversation in self.conversations:
            if conversation.id == conversation_id:
                self.current_conversation = conversation
                self._render_current_conversation()
                return

    def _resolve_model(self) -> str:
        if not self.models:
            raise ModelSelectionError(
                "Nenhum modelo disponível. Verifique o Ollama e instale um modelo."
            )
        if self.config.mode == "manual":
            selected = self.chat_view.model_combo.currentText().strip()
            if not selected:
                raise ModelSelectionError("Selecione um modelo no modo manual.")
            if selected not in {model.name for model in self.models}:
                raise ModelSelectionError("O modelo selecionado não está mais instalado.")
            self.config.manual_model = selected
            return selected
        return choose_model(self.models, self.config.preferred_model).name

    def _show_resource_protection(self, report: CompatibilityReport) -> None:
        """Explain a resource refusal and provide actionable next steps."""
        reasons = "\\n".join(f"• {reason}" for reason in report.reasons)
        alternatives = "\\n".join(
            f"• {item}" for item in report.recommendations
        )
        details = "\\n\\n".join(
            part for part in (reasons, alternatives) if part
        )

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Proteção de hardware")
        dialog.setText(
            report.user_message
            or "A solicitação foi bloqueada pela política de recursos."
        )
        dialog.setInformativeText(
            "Nenhuma mensagem foi enviada ao Ollama. Consulte os detalhes "
            "para entender o bloqueio e as alternativas."
        )
        if details:
            dialog.setDetailedText(details)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()
        self.chat_view.set_status("Geração bloqueada pela proteção de hardware")
        self.statusBar().showMessage(
            "Geração bloqueada: " + "; ".join(report.reasons), 15000
        )

    def send_message(self, text: str) -> None:
        if self._chat_worker is not None and self._chat_worker.isRunning():
            return
        if not text.strip():
            return
        try:
            model = self._resolve_model()
        except ModelSelectionError as exc:
            QMessageBox.information(self, "Modelo indisponível", str(exc))
            self.refresh_backend()
            return

        conversation = self.current_conversation
        messages: list[dict[str, Any]] = []
        if self.config.system_prompt.strip():
            messages.append({"role": "system", "content": self.config.system_prompt})
        messages.extend(conversation.messages)
        messages.append({"role": "user", "content": text.strip()})

        request = EngineRequest(
            model=model,
            messages=messages,
            options={"keep_alive": self.config.keep_alive},
        )
        try:
            hardware = detect_hardware()
            preferred_profile = (
                None if self.config.hardware_profile == "auto"
                else self.config.hardware_profile
            )
            request, report = OllamaEngine.prepare_resource_aware_request(
                request,
                hardware,
                preferred_profile=preferred_profile,
                protection_mode=self.config.protection_mode,
                requirements=ResourceRequirements(min_context_tokens=512),
            )
        except OllamaResourceProtectionError as exc:
            self._show_resource_protection(exc.report)
            return
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Não foi possível verificar o hardware",
                "A geração foi bloqueada porque o AILocal Universal não conseguiu "
                f"validar os recursos do computador.\\n\\n{exc}",
            )
            return

        conversation.messages.append({"role": "user", "content": text.strip()})
        if conversation.title == "Nova conversa":
            conversation.title = text.strip().splitlines()[0][:48]
        self._current_assistant_index = len(conversation.messages)
        conversation.messages.append({"role": "assistant", "content": ""})
        conversation.updated_at = datetime.now(UTC).isoformat()

        self._persist_conversations()
        self._refresh_history()
        self._render_current_conversation()
        worker = OllamaChatWorker(self.engine, request, self)
        self._chat_worker = worker
        worker.token.connect(self._on_chat_token)
        worker.completed.connect(self._on_chat_completed)
        worker.failed.connect(self._on_chat_error)
        worker.cancelled.connect(self._on_chat_cancelled)
        worker.finished.connect(lambda w=worker: self._chat_finished(w))
        self.chat_view.set_busy(True)
        self.chat_view.set_status(
            f"Perfil {report.selected_profile} · "
            f"contexto {report.budget.context_tokens} · "
            f"{report.budget.cpu_threads} thread(s) CPU"
        )
        self.statusBar().showMessage(
            f"Modelo: {model} · perfil {report.selected_profile} · "
            f"contexto {report.budget.context_tokens} · "
            f"{report.budget.cpu_threads} thread(s) CPU"
        )
        worker.start()

    def _assistant_message(self) -> dict[str, str] | None:
        index = self._current_assistant_index
        if index is None or index >= len(self.current_conversation.messages):
            return None
        return self.current_conversation.messages[index]

    def _discard_empty_assistant_message(self) -> None:
        index = self._current_assistant_index
        message = self._assistant_message()
        if index is not None and message is not None and not message.get("content"):
            self.current_conversation.messages.pop(index)
            self._render_current_conversation()

    def _on_chat_token(self, token: str) -> None:
        message = self._assistant_message()
        if message is None:
            return
        message["content"] += token
        self._render_current_conversation()

    def _on_chat_completed(self, metadata: object) -> None:
        self._persist_conversations()
        details = metadata if isinstance(metadata, dict) else {}
        eval_count = details.get("eval_count")
        eval_duration = details.get("eval_duration")
        suffix = ""
        if (
            isinstance(eval_count, (int, float))
            and isinstance(eval_duration, (int, float))
            and eval_duration > 0
        ):
            suffix = f" — {eval_count / (eval_duration / 1_000_000_000):.2f} tokens/s"
        self.chat_view.set_status("Resposta concluída" + suffix)
        self.statusBar().showMessage("Geração concluída" + suffix, 8000)

    def _on_chat_error(self, message: str) -> None:
        self._discard_empty_assistant_message()
        self._persist_conversations()
        self.chat_view.set_status("Falha na geração")
        self.statusBar().showMessage(message, 15000)
        QMessageBox.warning(self, "Falha no Ollama", message)

    def _on_chat_cancelled(self) -> None:
        self._discard_empty_assistant_message()
        self._persist_conversations()
        self.chat_view.set_status("Geração cancelada")
        self.statusBar().showMessage("Geração cancelada", 5000)

    def _chat_finished(self, worker: OllamaChatWorker) -> None:
        if self._chat_worker is worker:
            self._chat_worker = None
            self._current_assistant_index = None
            self.chat_view.set_busy(False)
        worker.deleteLater()

    def cancel_generation(self) -> None:
        if self._chat_worker is not None:
            self.chat_view.set_status("Cancelando…")
            self._chat_worker.cancel()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._chat_worker is not None and self._chat_worker.isRunning():
            self._chat_worker.cancel()
            self._chat_worker.wait(5000)
        if self._status_worker is not None and self._status_worker.isRunning():
            self._status_worker.cancel()
            self._status_worker.wait(2000)
        event.accept()
