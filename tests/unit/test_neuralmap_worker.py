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
