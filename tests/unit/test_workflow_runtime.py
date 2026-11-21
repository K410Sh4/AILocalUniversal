import pytest
from workflows.graph import WorkflowGraph
from workflows.runtime import GraphRuntime, HandlerRegistry


TEMPLATE = "workflows/templates/multi_specialist.pipeline.graph.json"


@pytest.mark.asyncio
async def test_review_loop_restores_best_outputs_with_custom_node_ids() -> None:
    graph = WorkflowGraph.load(TEMPLATE)
    id_map = {
        "code": "code_custom",
        "chat": "chat_custom",
        "image": "image_custom",
        "review": "review_custom",
        "revision_loop": "loop_custom",
    }
    for node in graph.nodes:
        previous_id = node.node_id
        node.node_id = id_map.get(previous_id, previous_id)
        if node.node_type.startswith("specialist."):
            node.config["use_resource_budget"] = False
        if node.node_type == "hardware.profile":
            node.enabled = False
        if node.node_type == "control.loop":
            node.config["max_iterations"] = 2
            node.config["review_node_id"] = id_map["review"]
            node.config["default_retry_targets"] = [id_map["code"]]
    for edge in graph.edges:
        edge.source = id_map.get(edge.source, edge.source)
        edge.target = id_map.get(edge.target, edge.target)

    calls = {"code": 0, "chat": 0, "review": 0}

    async def code_handler(_node, _inputs, _context):
        calls["code"] += 1
        value = f"code-v{calls['code']}"
        return {"code": value, "text": value}

    async def chat_handler(_node, inputs, _context):
        calls["chat"] += 1
        value = f"explanation-for-{inputs['code']}"
        return {"explanation": value, "text": value}

    async def review_handler(_node, _inputs, _context):
        calls["review"] += 1
        return {
            "decision": {
                "approved": False,
                "score": 0.9 if calls["review"] == 1 else 0.7,
                "feedback": "Revise o código.",
                "retry_targets": [id_map["code"]],
                "notes": "A primeira versão teve a melhor nota.",
            }
        }

    handlers = HandlerRegistry()
    handlers.register("specialist.code", code_handler)
    handlers.register("specialist.chat", chat_handler)
    handlers.register("specialist.review", review_handler)

    result = await GraphRuntime(handlers).run(
        graph,
        "Crie uma solução e explique-a.",
    )

    assert result.success is True
    assert calls["review"] == 2
    assert result.output["code"] == "code-v1"
    assert result.output["explanation"] == "explanation-for-code-v1"
    assert result.output["review"]["convergence"] == "limit_reached"
    assert result.output["review"]["best_iteration"] == 1
