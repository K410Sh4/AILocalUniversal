import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from app.views.neuralmap_view import NeuralMapView


@pytest.fixture(scope="module")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def test_neuralmap_view_initializes_template_and_undo_redo(qapp):
    view = NeuralMapView()
    try:
        assert isinstance(view.undo_button, QPushButton)
        assert isinstance(view.redo_button, QPushButton)
        assert not view.undo_button.isEnabled()
        assert not view.redo_button.isEnabled()

        view.apply_template()

        assert view.graph.graph_id == "multi-specialist-reference"
        assert view.validate_current_graph()
        assert len(view.canvas.node_items) == len(view.graph.nodes) == 10
        assert len(view.canvas.connection_items) == len(view.graph.edges) == 24
        assert view.undo_button.isEnabled()
        assert not view.redo_button.isEnabled()

        view.undo_stack.undo()
        assert view.graph.graph_id == "new-workflow"
        assert len(view.canvas.node_items) == 2
        assert view.redo_button.isEnabled()

        view.undo_stack.redo()
        assert view.graph.graph_id == "multi-specialist-reference"
        assert len(view.canvas.connection_items) == 24
    finally:
        view.close()
