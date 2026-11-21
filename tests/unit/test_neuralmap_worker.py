from workers.neuralmap_worker import NeuralMapWorker
from workflows.graph import GraphNode, WorkflowGraph
from workflows.runtime import GraphRuntime, HandlerRegistry


def test_worker_uses_immutable_graph_snapshot() -> None:
    graph = WorkflowGraph(
        graph_id="snapshot-test",
        name="Original",
        nodes=[
            GraphNode.create("input", "input.text", label="Original input"),
            GraphNode.create("response", "output.response", label="Original output"),
        ],
        edges=[],
    )

    worker = NeuralMapWorker(
        GraphRuntime(HandlerRegistry()),
        graph,
        "Executar snapshot",
        dry_run=True,
    )
    graph.name = "Alterado"
    graph.nodes[0].label = "Alterado depois do início"

    assert worker.graph.name == "Original"
    assert worker.graph.nodes[0].label == "Original input"
    assert worker.input_text == "Executar snapshot"



def test_worker_cancel_tolerates_event_loop_shutdown_race() -> None:
    class ClosedLoop:
        def call_soon_threadsafe(self, _callback) -> None:
            raise RuntimeError("event loop is closed")

    class PendingTask:
        def done(self) -> bool:
            return False

    graph = WorkflowGraph(
        graph_id="cancel-race",
        name="Cancel race",
        nodes=[GraphNode.create("input", "input.text")],
        edges=[],
    )
    worker = NeuralMapWorker(
        GraphRuntime(HandlerRegistry()),
        graph,
        "input",
        dry_run=True,
    )
    worker._loop = ClosedLoop()
    worker._task = PendingTask()

    worker.cancel()

    assert worker._cancel_requested.is_set()
