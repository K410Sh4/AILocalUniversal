import asyncio
import json
from pathlib import Path

import pytest

from workflows.graph import (
    EdgeType,
    GraphEdge,
    GraphError,
    WorkflowGraph,
    topological_order,
    validate_graph,
)
from workflows.runtime import GraphRuntime, HandlerRegistry

TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "workflows"
    / "multi_specialist.pipeline.graph.json"
)


def load_template() -> WorkflowGraph:
    return WorkflowGraph.load(TEMPLATE)


def test_reference_template_is_valid_and_has_explicit_bounded_loop():
    graph = load_template()
    validate_graph(graph)

    loop = next(node for node in graph.nodes if node.node_type == "control.loop")
    assert loop.config["max_iterations"] == 3
    assert loop.config["review_node_id"] == "review"
    repeat_edges = [
        edge for edge in graph.edges
        if edge.source == loop.node_id and edge.source_port == "repeat"
    ]
    assert len(repeat_edges) == 3
    assert "revision_loop" in topological_order(graph)


def test_unknown_node_type_is_rejected():
    data = load_template().to_dict()
    data["nodes"].append(
        {
            "id": "danger",
            "type": "python.exec",
            "label": "Arbitrary execution",
            "enabled": True,
            "config": {},
            "ui": {"position": {"x": 0, "y": 0}},
        }
    )

    with pytest.raises(GraphError) as exc_info:
        WorkflowGraph.from_dict(data)

    assert exc_info.value.reason_code == "UNKNOWN_NODE_TYPE"


def test_uncontrolled_cycle_is_rejected():
    graph = load_template()
    graph.edges.append(
        GraphEdge(
            edge_id="uncontrolled-cycle",
            source="chat",
            source_port="explanation",
            target="code",
            target_port="feedback",
            edge_type=EdgeType.ALWAYS,
        )
    )

    with pytest.raises(GraphError) as exc_info:
        validate_graph(graph)

    assert exc_info.value.reason_code == "UNCONTROLLED_CYCLE"


def test_graph_json_round_trip_preserves_layout_and_ports():
    graph = load_template()
    serialized = json.loads(json.dumps(graph.to_dict(), ensure_ascii=False))
    rebuilt = WorkflowGraph.from_dict(serialized)

    assert rebuilt.graph_id == graph.graph_id
    assert rebuilt.to_dict() == graph.to_dict()
    assert rebuilt.nodes[0].position == graph.nodes[0].position


@pytest.mark.asyncio
async def test_dry_run_executes_reference_template_without_external_engines():
    graph = load_template()
    result = await GraphRuntime().run(
        graph,
        "Crie uma aplicação de lista de tarefas com explicação e imagem.",
        dry_run=True,
    )

    assert result.success
    assert result.output["code"]
    assert result.output["explanation"].startswith("[DRY-RUN")
    assert result.output["image"]["status"] == "not_generated"
    assert result.output["review"]["approved"] is True
    assert result.output["review"]["iterations"] == 1
    assert result.output["trace_id"] == result.trace_id


class ScriptedSpecialists:
    def __init__(self, *, approve_on: int = 2, scores=None):
        self.calls = {"code": 0, "chat": 0, "image": 0, "review": 0}
        self.approve_on = approve_on
        self.scores = list(scores or [0.5, 0.8, 0.7])

    async def __call__(self, node, inputs, context):
        kind = node.node_type
        self.calls[kind.split(".")[-1]] += 1
        count = self.calls[kind.split(".")[-1]]
        if kind == "specialist.code":
            value = f"code-version-{count}"
            return {"code": value, "text": value}
        if kind == "specialist.chat":
            return {"explanation": f"explanation-version-{count}", "text": "explanation"}
        if kind == "specialist.image":
            image = {"artifact_id": f"image-{count}", "mime_type": "image/png"}
            return {"image": image, "artifact": image}
        if kind == "specialist.review":
            review_count = self.calls["review"]
            approved = review_count >= self.approve_on
            score = self.scores[min(review_count - 1, len(self.scores) - 1)]
            return {
                "decision": {
                    "approved": approved,
                    "score": score,
                    "notes": "Revisão de teste",
                    "feedback": "Atualize o código e os itens dependentes.",
                    "retry_targets": ["code"],
                }
            }
        raise AssertionError(f"Unexpected node type: {kind}")


def scripted_registry(specialists):
    registry = HandlerRegistry()
    for node_type in (
        "specialist.code",
        "specialist.chat",
        "specialist.image",
        "specialist.review",
    ):
        registry.register(node_type, specialists)
    return registry


@pytest.mark.asyncio
async def test_review_loop_reexecutes_only_requested_target_and_dependants():
    graph = load_template()
    specialists = ScriptedSpecialists(approve_on=2)
    result = await GraphRuntime(scripted_registry(specialists)).run(
        graph,
        "Implemente um sistema simples.",
    )

    assert result.success
    assert result.output["review"]["approved"] is True
    assert result.output["review"]["iterations"] == 2
    assert result.output["code"] == "code-version-2"
    assert specialists.calls == {"code": 2, "chat": 2, "image": 2, "review": 2}


@pytest.mark.asyncio
async def test_review_loop_uses_best_scored_bundle_at_iteration_limit():
    graph = load_template()
    loop = next(node for node in graph.nodes if node.node_type == "control.loop")
    loop.config["max_iterations"] = 3
    specialists = ScriptedSpecialists(
        approve_on=99,
        scores=[0.9, 0.4, 0.2],
    )
    result = await GraphRuntime(scripted_registry(specialists)).run(
        graph,
        "Crie uma solução e revise.",
    )

    assert result.success
    assert result.output["code"] == "code-version-1"
    assert result.output["review"]["approved"] is False
    assert result.output["review"]["convergence"] == "limit_reached"
    assert result.output["review"]["iterations"] == 3
    assert result.output["review"]["best_iteration"] == 1
    assert "não convergente" in result.output["review"]["notes"]


@pytest.mark.asyncio
async def test_missing_required_backend_returns_stable_reason_code():
    graph = load_template()
    result = await GraphRuntime().run(graph, "Teste", dry_run=False)

    assert not result.success
    assert result.error["reason_code"] == "ENGINE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_optional_image_backend_failure_does_not_abort_graph():
    graph = load_template()
    specialists = ScriptedSpecialists(approve_on=1)
    registry = scripted_registry(specialists)
    registry._handlers.pop("specialist.image")
    result = await GraphRuntime(registry).run(graph, "Teste")

    assert result.success
    assert result.output["image"] is None


@pytest.mark.asyncio
async def test_pre_cancelled_graph_returns_cancellation_reason():
    graph = load_template()
    cancel = asyncio.Event()
    cancel.set()
    result = await GraphRuntime().run(graph, "Teste", dry_run=True, cancel_event=cancel)

    assert not result.success
    assert result.error["reason_code"] == "EXECUTION_CANCELLED"



def test_missing_required_input_connection_is_rejected():
    graph = load_template()
    graph.edges = [edge for edge in graph.edges if edge.edge_id != "e02"]

    with pytest.raises(GraphError) as exc_info:
        validate_graph(graph)

    assert exc_info.value.reason_code == "REQUIRED_INPUT_CONNECTION_MISSING"


def test_node_enabled_flag_must_be_boolean():
    data = load_template().to_dict()
    data["nodes"][0]["enabled"] = "false"

    with pytest.raises(GraphError) as exc_info:
        WorkflowGraph.from_dict(data)

    assert exc_info.value.reason_code == "INVALID_NODE_ENABLED"


def test_non_finite_layout_coordinates_are_rejected():
    data = load_template().to_dict()
    data["nodes"][0]["ui"]["position"]["x"] = float("nan")

    with pytest.raises(GraphError) as exc_info:
        WorkflowGraph.from_dict(data)

    assert exc_info.value.reason_code == "INVALID_NODE_POSITION"


def test_graph_metadata_must_be_an_object():
    data = load_template().to_dict()
    data["metadata"] = ["not", "an", "object"]

    with pytest.raises(GraphError) as exc_info:
        WorkflowGraph.from_dict(data)

    assert exc_info.value.reason_code == "INVALID_GRAPH_METADATA"



def test_unhashable_hardware_profile_config_is_rejected():
    data = load_template().to_dict()
    hardware = next(
        node for node in data["nodes"] if node["type"] == "hardware.profile"
    )
    hardware["config"]["profile"] = ["auto"]

    with pytest.raises(GraphError) as exc_info:
        WorkflowGraph.from_dict(data)

    assert exc_info.value.reason_code == "INVALID_HARDWARE_PROFILE"


def test_unhashable_protection_mode_config_is_rejected():
    data = load_template().to_dict()
    hardware = next(
        node for node in data["nodes"] if node["type"] == "hardware.profile"
    )
    hardware["config"]["protection_mode"] = {"mode": "protected"}

    with pytest.raises(GraphError) as exc_info:
        WorkflowGraph.from_dict(data)

    assert exc_info.value.reason_code == "INVALID_PROTECTION_MODE"
