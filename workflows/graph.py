"""Versioned, declarative workflow graph model and static validator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


GRAPH_FORMAT = "ailocal.pipeline-graph"
GRAPH_VERSION = "1.0"


class EdgeType(StrEnum):
    ALWAYS = "always"
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"


class GraphError(ValueError):
    """Stable, user-safe validation or serialization error."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        alternatives: tuple[str, ...] = (),
    ) -> None:
        self.reason_code = reason_code
        self.message = message
        self.alternatives = alternatives
        super().__init__(f"{reason_code}: {message}")


@dataclass(frozen=True)
class NodeTypeSpec:
    inputs: frozenset[str]
    outputs: frozenset[str]
    category: str


NODE_SPECS: dict[str, NodeTypeSpec] = {
    "input.text": NodeTypeSpec(frozenset(), frozenset({"text"}), "input"),
    "input.attachment": NodeTypeSpec(
        frozenset(), frozenset({"attachment"}), "input"
    ),
    "specialist.code": NodeTypeSpec(
        frozenset({"text", "context", "feedback", "budget"}),
        frozenset({"code", "text", "artifacts"}),
        "specialist",
    ),
    "specialist.chat": NodeTypeSpec(
        frozenset({"text", "code", "context", "feedback", "budget"}),
        frozenset({"explanation", "text"}),
        "specialist",
    ),
    "specialist.image": NodeTypeSpec(
        frozenset({"prompt", "code", "explanation", "context", "feedback", "budget"}),
        frozenset({"image", "artifact"}),
        "specialist",
    ),
    "specialist.review": NodeTypeSpec(
        frozenset({"code", "explanation", "image", "context", "budget"}),
        frozenset({"decision", "approved", "feedback", "retry_targets", "score", "notes"}),
        "specialist",
    ),
    "control.loop": NodeTypeSpec(
        frozenset({"decision"}),
        frozenset({"repeat", "decision"}),
        "control",
    ),
    "filter.context": NodeTypeSpec(
        frozenset({"text", "content", "context"}),
        frozenset({"text", "context"}),
        "filter",
    ),
    "hardware.profile": NodeTypeSpec(
        frozenset(), frozenset({"budget", "report"}), "hardware"
    ),
    "merge.outputs": NodeTypeSpec(
        frozenset({"code", "explanation", "image", "review"}),
        frozenset({"result"}),
        "output",
    ),
    "output.response": NodeTypeSpec(
        frozenset({"result"}), frozenset({"response"}), "output"
    ),
    "output.trace": NodeTypeSpec(
        frozenset({"trace"}), frozenset({"trace"}), "output"
    ),
}

_SPECIALIST_DEFAULTS: dict[str, Any] = {
    "engine": "ollama",
    "model_id": "qwen2.5:7b",
    "system_prompt": "",
    "plugin_ref": None,
    "generation": {"temperature": 0.2, "num_predict": 2048},
    "use_resource_budget": True,
    "optional": False,
}

DEFAULT_NODE_CONFIGS: dict[str, dict[str, Any]] = {
    "input.text": {"required": True},
    "input.attachment": {"required": False, "max_size_mb": 25},
    "specialist.code": {**_SPECIALIST_DEFAULTS, "model_id": "qwen2.5:7b"},
    "specialist.chat": {
        **_SPECIALIST_DEFAULTS,
        "model_id": "deepseek-r1:7b",
        "generation": {"temperature": 0.4, "num_predict": 2048},
    },
    "specialist.image": {
        **_SPECIALIST_DEFAULTS,
        "engine": "image",
        "model_id": "flux.1",
        "generation": {"steps": 24, "width": 1024, "height": 1024},
    },
    "specialist.review": {
        **_SPECIALIST_DEFAULTS,
        "model_id": "qwen2.5:7b",
        "generation": {"temperature": 0.1, "num_predict": 1200},
    },
    "control.loop": {
        "max_iterations": 3,
        "review_node_id": "review",
        "default_retry_targets": ["code", "chat", "image"],
        "stop_condition": "approved",
    },
    "filter.context": {"max_characters": 24000, "preserve_attachments": True},
    "hardware.profile": {"profile": "auto", "protection_mode": "protected"},
    "merge.outputs": {"include_trace": True},
    "output.response": {"format": "structured"},
    "output.trace": {"enabled": True},
}


@dataclass(slots=True)
class GraphNode:
    node_id: str
    node_type: str
    label: str
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    position: dict[str, float] = field(
        default_factory=lambda: {"x": 0.0, "y": 0.0}
    )
    color: str | None = None

    @classmethod
    def create(
        cls,
        node_id: str,
        node_type: str,
        *,
        label: str | None = None,
        config: dict[str, Any] | None = None,
        position: tuple[float, float] = (0.0, 0.0),
    ) -> GraphNode:
        if node_type not in NODE_SPECS:
            raise GraphError(
                "UNKNOWN_NODE_TYPE",
                f"Tipo de nó desconhecido: {node_type}.",
                ("Use um dos tipos registrados na biblioteca NeuralMap.",),
            )
        merged = json.loads(json.dumps(DEFAULT_NODE_CONFIGS[node_type]))
        if config:
            merged.update(config)
        return cls(
            node_id=node_id,
            node_type=node_type,
            label=label or node_type,
            config=merged,
            position={"x": float(position[0]), "y": float(position[1])},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "type": self.node_type,
            "label": self.label,
            "enabled": self.enabled,
            "config": self.config,
            "ui": {
                "position": {
                    "x": self.position["x"],
                    "y": self.position["y"],
                },
                **({"color": self.color} if self.color else {}),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphNode:
        if not isinstance(data, dict):
            raise GraphError("INVALID_NODE", "Cada nó deve ser um objeto JSON.")
        node_type = data.get("type")
        if node_type not in NODE_SPECS:
            raise GraphError(
                "UNKNOWN_NODE_TYPE",
                f"Tipo de nó desconhecido: {node_type}.",
                ("Atualize o AILocal Universal ou remova o nó desconhecido.",),
            )
        ui = data.get("ui") or {}
        position = ui.get("position") or {"x": 0.0, "y": 0.0}
        config = data.get("config") or {}
        if not isinstance(config, dict):
            raise GraphError("INVALID_NODE_CONFIG", "A configuração do nó deve ser um objeto.")
        node = cls(
            node_id=str(data.get("id", "")),
            node_type=str(node_type),
            label=str(data.get("label") or node_type),
            enabled=bool(data.get("enabled", True)),
            config=dict(config),
            position={
                "x": float(position.get("x", 0.0)),
                "y": float(position.get("y", 0.0)),
            },
            color=ui.get("color"),
        )
        _validate_node_config(node)
        return node


@dataclass(slots=True)
class GraphEdge:
    edge_id: str
    source: str
    source_port: str
    target: str
    target_port: str
    edge_type: EdgeType = EdgeType.ALWAYS

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.edge_id,
            "source": self.source,
            "source_port": self.source_port,
            "target": self.target,
            "target_port": self.target_port,
            "edge_type": self.edge_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphEdge:
        try:
            return cls(
                edge_id=str(data["id"]),
                source=str(data["source"]),
                source_port=str(data["source_port"]),
                target=str(data["target"]),
                target_port=str(data["target_port"]),
                edge_type=EdgeType(data.get("edge_type", "always")),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise GraphError(
                "INVALID_EDGE",
                "A conexão possui campos ausentes ou tipo de aresta inválido.",
                ("Revise os nós de origem/destino, portas e edge_type.",),
            ) from exc


@dataclass(slots=True)
class WorkflowGraph:
    graph_id: str
    name: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    graph_version: str = GRAPH_VERSION
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": GRAPH_FORMAT,
            "version": self.graph_version,
            "id": self.graph_id,
            "name": self.name,
            "description": self.description,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowGraph:
        if not isinstance(data, dict) or data.get("format") != GRAPH_FORMAT:
            raise GraphError(
                "UNSUPPORTED_GRAPH_FORMAT",
                "O arquivo não é um NeuralMap pipeline graph compatível.",
            )
        version = str(data.get("version", ""))
        if version.split(".", 1)[0] != GRAPH_VERSION.split(".", 1)[0]:
            raise GraphError(
                "UNSUPPORTED_GRAPH_VERSION",
                f"Versão de grafo não suportada: {version}.",
                ("Atualize o AILocal Universal para abrir este mapa.",),
            )
        try:
            graph = cls(
                graph_id=str(data["id"]),
                name=str(data["name"]),
                description=str(data.get("description", "")),
                graph_version=version,
                nodes=[GraphNode.from_dict(item) for item in data["nodes"]],
                edges=[GraphEdge.from_dict(item) for item in data["edges"]],
                metadata=dict(data.get("metadata", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, GraphError):
                raise
            raise GraphError("INVALID_GRAPH", "A estrutura do grafo está incompleta.") from exc
        validate_graph(graph)
        return graph

    @classmethod
    def load(cls, path: str | Path) -> WorkflowGraph:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GraphError(
                "GRAPH_READ_ERROR",
                f"Não foi possível abrir o NeuralMap: {exc}",
            ) from exc
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        validate_graph(self)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)


def _validate_node_config(node: GraphNode) -> None:
    config = node.config
    if node.node_type.startswith("specialist."):
        if node.enabled:
            for key in ("engine", "model_id"):
                if not isinstance(config.get(key), str) or not config[key].strip():
                    raise GraphError(
                        "SPECIALIST_CONFIG_INCOMPLETE",
                        f"O nó '{node.label}' precisa definir engine e model_id.",
                        ("Escolha um backend/modelo instalado ou desabilite o nó opcional.",),
                    )
        if config.get("plugin_ref") is not None and not isinstance(config["plugin_ref"], str):
            raise GraphError("INVALID_PLUGIN_REF", "plugin_ref deve ser um identificador textual.")
        generation = config.get("generation", {})
        if not isinstance(generation, dict):
            raise GraphError(
                "INVALID_GENERATION_CONFIG",
                f"Os parâmetros de geração de '{node.label}' devem ser um objeto.",
            )
    if node.node_type == "control.loop":
        maximum = config.get("max_iterations", 3)
        if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 20:
            raise GraphError(
                "INVALID_LOOP_LIMIT",
                "max_iterations deve ser um inteiro entre 1 e 20.",
            )
        if config.get("stop_condition", "approved") != "approved":
            raise GraphError(
                "UNSUPPORTED_LOOP_CONDITION",
                "A versão 1 aceita somente a condição de parada 'approved'.",
            )
    if node.node_type == "hardware.profile":
        if config.get("profile", "auto") not in {
            "auto", "ultra_light", "minimal", "balanced", "performance", "max_quality"
        }:
            raise GraphError("INVALID_HARDWARE_PROFILE", "Perfil de hardware desconhecido.")
        if config.get("protection_mode", "protected") not in {
            "permissive", "adaptive", "protected"
        }:
            raise GraphError("INVALID_PROTECTION_MODE", "Modo de proteção desconhecido.")


def _is_loop_back_edge(edge: GraphEdge, nodes: dict[str, GraphNode]) -> bool:
    source = nodes.get(edge.source)
    return bool(
        source
        and source.node_type == "control.loop"
        and edge.source_port == "repeat"
    )


def topological_order(graph: WorkflowGraph) -> list[str]:
    """Return DAG order after excluding the only permitted loop-back edges."""
    nodes = {node.node_id: node for node in graph.nodes if node.enabled}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for edge in graph.edges:
        if edge.source not in nodes or edge.target not in nodes:
            continue
        if _is_loop_back_edge(edge, nodes):
            continue
        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1

    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    result: list[str] = []
    while ready:
        current = ready.pop(0)
        result.append(current)
        for target in sorted(adjacency[current]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    if len(result) != len(nodes):
        raise GraphError(
            "UNCONTROLLED_CYCLE",
            "O grafo contém um ciclo que não passa por control.loop.repeat.",
            ("Remova o ciclo ou conecte o retorno por um nó control.loop explícito.",),
        )
    return result


def validate_graph(graph: WorkflowGraph) -> None:
    if graph.graph_version != GRAPH_VERSION:
        raise GraphError(
            "UNSUPPORTED_GRAPH_VERSION",
            f"Versão não suportada: {graph.graph_version}.",
        )
    if not graph.graph_id or not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", graph.graph_id):
        raise GraphError("INVALID_GRAPH_ID", "O identificador do grafo é inválido.")
    if not graph.name.strip():
        raise GraphError("INVALID_GRAPH_NAME", "O grafo precisa ter um nome.")
    node_map: dict[str, GraphNode] = {}
    for node in graph.nodes:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", node.node_id):
            raise GraphError("INVALID_NODE_ID", f"Identificador de nó inválido: {node.node_id}.")
        if node.node_id in node_map:
            raise GraphError("DUPLICATE_NODE_ID", f"ID de nó duplicado: {node.node_id}.")
        if node.node_type not in NODE_SPECS:
            raise GraphError("UNKNOWN_NODE_TYPE", f"Tipo desconhecido: {node.node_type}.")
        if not node.label.strip():
            raise GraphError("INVALID_NODE_LABEL", "Todo nó precisa ter um rótulo.")
        _validate_node_config(node)
        node_map[node.node_id] = node

    if not graph.nodes:
        raise GraphError("EMPTY_GRAPH", "O NeuralMap não contém nós.")

    edge_ids: set[str] = set()
    seen_edges: set[tuple[str, str, str, str]] = set()
    loop_nodes = [
        node for node in graph.nodes
        if node.enabled and node.node_type == "control.loop"
    ]
    if len(loop_nodes) > 1:
        raise GraphError(
            "MULTIPLE_LOOPS_UNSUPPORTED",
            "A versão 1 permite um controlador de loop por grafo.",
            ("Combine as revisões em um único specialist.review e control.loop.",),
        )

    for edge in graph.edges:
        if edge.edge_id in edge_ids:
            raise GraphError("DUPLICATE_EDGE_ID", f"ID de conexão duplicado: {edge.edge_id}.")
        edge_ids.add(edge.edge_id)
        signature = (edge.source, edge.source_port, edge.target, edge.target_port)
        if signature in seen_edges:
            raise GraphError("DUPLICATE_EDGE", "Existe uma conexão duplicada.")
        seen_edges.add(signature)
        if edge.source not in node_map or edge.target not in node_map:
            raise GraphError("EDGE_NODE_MISSING", "Uma conexão referencia um nó inexistente.")
        source_spec = NODE_SPECS[node_map[edge.source].node_type]
        target_spec = NODE_SPECS[node_map[edge.target].node_type]
        if edge.source_port not in source_spec.outputs:
            raise GraphError(
                "INVALID_SOURCE_PORT",
                f"Porta de saída '{edge.source_port}' não existe em {node_map[edge.source].node_type}.",
            )
        if edge.target_port not in target_spec.inputs:
            raise GraphError(
                "INVALID_TARGET_PORT",
                f"Porta de entrada '{edge.target_port}' não existe em {node_map[edge.target].node_type}.",
            )
        if _is_loop_back_edge(edge, node_map):
            if node_map[edge.target].node_type not in {
                "specialist.code", "specialist.chat", "specialist.image"
            } or edge.target_port != "feedback":
                raise GraphError(
                    "INVALID_LOOP_BACK_EDGE",
                    "control.loop.repeat só pode retornar a uma porta feedback de especialista.",
                )

    if loop_nodes:
        loop = loop_nodes[0]
        incoming_review = [
            edge for edge in graph.edges
            if edge.target == loop.node_id and edge.target_port == "decision"
        ]
        review_id = loop.config.get("review_node_id")
        if not any(
            node_map[edge.source].node_type == "specialist.review"
            and edge.source == review_id
            and edge.edge_type == EdgeType.ON_FAILURE
            for edge in incoming_review
        ):
            raise GraphError(
                "LOOP_REVIEW_LINK_MISSING",
                "control.loop precisa receber a decisão on_failure do specialist.review declarado.",
            )
        if not any(
            _is_loop_back_edge(edge, node_map) for edge in graph.edges
        ):
            raise GraphError(
                "LOOP_BACK_EDGE_MISSING",
                "control.loop não possui retorno para nenhum especialista.",
            )

    enabled_types = {node.node_type for node in graph.nodes if node.enabled}
    if "input.text" not in enabled_types:
        raise GraphError("TEXT_INPUT_MISSING", "O grafo precisa de ao menos um nó input.text.")
    if "output.response" not in enabled_types:
        raise GraphError("RESPONSE_OUTPUT_MISSING", "O grafo precisa de um nó output.response.")

    order = topological_order(graph)
    enabled = {node.node_id: node for node in graph.nodes if node.enabled}
    positions = {node_id: index for index, node_id in enumerate(order)}
    for edge in graph.edges:
        if edge.source not in enabled or edge.target not in enabled:
            continue
        if _is_loop_back_edge(edge, enabled):
            continue
        if positions[edge.source] >= positions[edge.target]:
            raise GraphError(
                "INVALID_GRAPH_ORDER",
                "As dependências do grafo não formam uma ordem de execução válida.",
            )
