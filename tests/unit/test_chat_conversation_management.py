from PySide6.QtWidgets import QApplication

from app.views.chat_view import ChatView


def test_chat_view_emits_id_for_selected_conversation_deletion() -> None:
    app = QApplication.instance() or QApplication([])
    view = ChatView()
    view.set_history([("conversation-1", "Conversa de teste")], "conversation-1")
    emitted: list[str] = []
    view.delete_conversation_requested.connect(emitted.append)

    assert view.delete_button.isEnabled()
    view.delete_button.click()

    assert emitted == ["conversation-1"]
    view.set_history([], None)
    assert not view.delete_button.isEnabled()
    view.close()
    app.processEvents()
