"""UI-independent, asynchronous workflow graph runtime."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from core.neuralinjector.resources import (
    ProtectionMode,
    ResourceRequirements,
    build_compatibility_report,
    detect_hardware,
)
from core.execution_trace import ExecutionTrace
from workflows.graph import (
    EdgeType,
    GraphEdge,
    GraphError,
    GraphNode,
    NODE_SPECS,
    WorkflowGraph,
    topological_order,
    validate_graph,
)


@dataclass(slots=True)
class NodeContext:
    trace_id: str
    input_text: str
    attachments: list[dict[str, Any]]
    dry_run: bool
    cancel_event: asyncio.Event
    graph_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GraphRunResult:
    trace_id: str
    success: bool
    output: dict[str, Any] | None
    trace: list[dict[str, Any]]
    error: dict[str, str] | None = None


class NodeHandler(Protocol):
    async def __call__(
        self,
        node: GraphNode,
        inputs: dict[str, Any],
        context: NodeContext,
    ) -> dict[str, Any]: ...


class HandlerRegistry:
    """Allowlisted node handler registry; graph files never provide executable code."""

    def __init__(self) -> None:
        self._handlers: dict[str, NodeHandler] = {}

    def register(self, node_type: str, handler: NodeHandler) -> None:
        if node_type not in NODE_SPECS:
            raise GraphError(
                "UNKNOWN_NODE_TYPE",
                f"Não é possível registrar handler para {node_type}.",
            )
        self._handlers[node_type] = handler

    def get(self, node_type: str) -> NodeHandler | None:
        return self._handlers.get(node_type)


EventCallback = Callable[[str, str, dict[str, Any]], None]


class GraphRuntime:
    """Sequential v1 executor with explicit, bounded review-loop semantics."""

    def __init__(
        self,
        handlers: HandlerRegistry | None = None,
        *,
        on_event: EventCallback | None = None,
    ) -> None:
        self.handlers = handlers or HandlerRegistry()
        self.on_event = on_event

    async def run(
        self,
        graph: WorkflowGraph,
        input_text: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        dry_run: bool = False,
        cancel_event: asyncio.Event | None = None,
    ) -> GraphRunResult:
        trace_id = str(uuid4())
        trace = ExecutionTrace()
        cancellation = cancel_event or asyncio.Event()
        context = NodeContext(
            trace_id=trace_id,
            input_text=input_text,
            attachments=list(attachments or []),
            dry_run=dry_run,
            cancel_event=cancellation,
            graph_metadata=dict(graph.metadata),
        )
        outputs: dict[str, dict[str, Any]] = {}
        outcomes: dict[str, bool] = {}
        nodes = {node.node_id: node for node in graph.nodes}
        enabled = {node_id: node for node_id, node in nodes.items() if node.enabled}
        order = topological_order(graph)
        loop_nodes = [
            node for node in enabled.values() if node.node_type == "control.loop"
        ]
        loop_node = loop_nodes[0] if loop_nodes else None
        loop_count = 0
        best_bundle: dict[str, dict[str, Any]] = {}
        best_score = float("-inf")
        best_iteration = 0
        review_decision: dict[str, Any] = {}
        review_runs = 0
        pending_feedback: dict[str, Any] = {}
        pass_filter: set[str] | None = None

        self._emit(trace, "graph", "started", {"dry_run": dry_run})
        try:
            validate_graph(graph)
            if not input_text.strip():
                raise GraphError("EMPTY_INPUT", "Digite uma solicitação antes de executar o mapa.")
            while True:
                if cancellation.is_set():
                    raise GraphError("EXECUTION_CANCELLED", "A execução do NeuralMap foi cancelada.")
                repeat_requested = False

                for node_id in order:
                    node = enabled[node_id]
                    if pass_filter is not None and node_id not in pass_filter:
                        continue
                    if node.node_type in {"merge.outputs", "output.response", "output.trace"}:
                        if loop_node and loop_count > 0 and review_decision.get("approved") is False:
                            # Finalization runs only after approval or loop exhaustion.
                            if node.node_type in {"merge.outputs", "output.response"}:
                                pass
                    incoming = self._incoming(graph.edges, node_id)
                    node_inputs = self._collect_inputs(
                        incoming,
                        outputs,
                        outcomes,
                        target_node=node_id,
                        include_loop_edges=True,
                    )
                    if node.node_type in {"input.text", "input.attachment", "hardware.profile"}:
                        pass
                    elif incoming and not node_inputs:
                        continue
                    if node_id in pending_feedback:
                        node_inputs["feedback"] = pending_feedback[node_id]

                    if node.node_type == "control.loop":
                        decision = node_inputs.get("decision")
                        if not isinstance(decision, dict):
                            continue
                        loop_count = max(loop_count, review_runs)
                        maximum = int(node.config.get("max_iterations", 3))
                        approved = decision.get("approved") is True
                        if approved:
                            loop_output = dict(decision)
                            loop_output.update(
                                {
                                    "approved": True,
                                    "iterations": review_runs,
                                    "convergence": "approved",
                                }
                            )
                            outputs[node_id] = {
                                "repeat": None,
                                "decision": loop_output,
                            }
                            outcomes[node_id] = True
                            continue

                        if loop_count < maximum:
                            targets = decision.get("retry_targets") or node.config.get(
                                "default_retry_targets", []
                            )
                            target_ids = self._resolve_retry_targets(
                                graph, node, targets
                            )
                            if not target_ids:
                                raise GraphError(
                                    "LOOP_TARGETS_EMPTY",
                                    "A revisão pediu nova tentativa, mas não há especialistas conectados.",
                                    ("Conecte control.loop.repeat a uma porta feedback de especialista.",),
                                )
                            feedback = {
                                "message": str(decision.get("feedback", "")),
                                "iteration": loop_count,
                                "notes": str(decision.get("notes", "")),
                                "targets": target_ids,
                            }
                            outputs[node_id] = {
                                "repeat": feedback,
                                "decision": dict(decision),
                            }
                            outcomes[node_id] = False
                            pending_feedback = {target_id: feedback for target_id in target_ids}
                            pass_filter = self._affected_nodes(
                                graph,
                                target_ids,
                                stop_at={"control.loop", "merge.outputs", "output.response", "output.trace"},
                            )
                            repeat_requested = True
                            self._emit(
                                trace,
                                node_id,
                                "repeat",
                                {"iteration": loop_count, "targets": target_ids},
                            )
                            break

                        final_decision = dict(decision)
                        final_decision.update(
                            {
                                "approved": False,
                                "iterations": review_runs,
                                "convergence": "limit_reached",
                                "notes": (
                                    str(decision.get("notes", "")).strip()
                                    + " Revisão não convergente: limite de iterações atingido."
                                ).strip(),
                                "best_iteration": best_iteration,
                            }
                        )
                        if best_bundle:
                            outputs.update(best_bundle)
                        outputs[node_id] = {"repeat": None, "decision": final_decision}
                        outcomes[node_id] = False
                        review_decision = final_decision
                        self._emit(
                            trace,
                            node_id,
                            "limit_reached",
                            {"iterations": review_runs, "best_iteration": best_iteration},
                        )
                        continue

                    self._check_cancel(cancellation, node_id)
                    try:
                        node_output = await self._execute_node(
                            node, node_inputs, context
                        )
                        if not isinstance(node_output, dict):
                            raise GraphError(
                                "INVALID_NODE_OUTPUT",
                                f"O nó '{node.label}' não retornou um objeto de saída.",
                            )
                        self._validate_outputs(node, node_output)
                        node_success = True
                        if node.node_type == "specialist.review":
                            decision = self._normalize_review(node_output, graph)
                            node_output = dict(node_output)
                            node_output["decision"] = decision
                            node_output["feedback"] = decision.get("feedback", "")
                            node_output["retry_targets"] = decision.get("retry_targets", [])
                            node_output["score"] = decision.get("score")
                            node_output["notes"] = decision.get("notes", "")
                            node_success = decision["approved"]
                            review_runs += 1
                            decision["iterations"] = review_runs
                            decision["convergence"] = (
                                "approved" if decision["approved"] else "pending"
                            )
                            node_output["decision"] = decision
                            review_decision = decision
                            score = decision.get("score")
                            if isinstance(score, (int, float)) and not isinstance(score, bool):
                                if score > best_score:
                                    best_score = float(score)
                                    best_iteration = review_runs
                                    best_bundle = {
                                        candidate_id: dict(outputs[candidate_id])
                                        for candidate_id in ("code", "chat", "image")
                                        if candidate_id in outputs
                                    }
                            elif not best_bundle:
                                best_bundle = {
                                    candidate_id: dict(outputs[candidate_id])
                                    for candidate_id in ("code", "chat", "image")
                                    if candidate_id in outputs
                                }
                                best_iteration = review_runs
                        outputs[node_id] = node_output
                        outcomes[node_id] = node_success
                        self._emit(trace, node_id, "completed", {"type": node.node_type})
                    except GraphError as exc:
                        if node.config.get("optional") is True:
                            outputs[node_id] = self._empty_optional_output(node)
                            outcomes[node_id] = True
                            self._emit(
                                trace,
                                node_id,
                                "optional_failed",
                                {"reason_code": exc.reason_code, "message": exc.message},
                            )
                            continue
                        raise
                    except Exception as exc:
                        if node.config.get("optional") is True:
                            outputs[node_id] = self._empty_optional_output(node)
                            outcomes[node_id] = True
                            self._emit(
                                trace,
                                node_id,
                                "optional_failed",
                                {"error_type": type(exc).__name__},
                            )
                            continue
                        raise GraphError(
                            "NODE_EXECUTION_FAILED",
                            f"Falha ao executar '{node.label}': {exc}",
                            ("Confira o backend, o modelo e a configuração do nó.",),
                        ) from exc

                if repeat_requested:
                    continue
                break

            if pass_filter is not None:
                # A retry pass executes only invalidated specialists and their
                # dependants. Final merge/response nodes are executed once after
                # that pass reaches approval or the iteration limit.
                for node_id in order:
                    node = enabled[node_id]
                    if node.node_type not in {
                        "merge.outputs", "output.response", "output.trace"
                    }:
                        continue
                    self._check_cancel(cancellation, node_id)
                    incoming = self._incoming(graph.edges, node_id)
                    node_inputs = self._collect_inputs(
                        incoming,
                        outputs,
                        outcomes,
                        target_node=node_id,
                        include_loop_edges=True,
                    )
                    if incoming and not node_inputs:
                        continue
                    final_output = await self._execute_node(node, node_inputs, context)
                    self._validate_outputs(node, final_output)
                    outputs[node_id] = final_output
                    outcomes[node_id] = True
                    self._emit(trace, node_id, "completed", {"type": node.node_type})
                pass_filter = None

            final_nodes = [
                node_id for node_id in order
                if node_id in outputs and nodes[node_id].node_type == "output.response"
            ]
            if not final_nodes:
                raise GraphError(
                    "OUTPUT_NOT_PRODUCED",
                    "O fluxo terminou sem produzir output.response.",
                    ("Revise as conexões condicionais até o nó de saída.",),
                )
            response = outputs[final_nodes[-1]].get("response")
            if not isinstance(response, dict):
                response = {"value": response}
            response.setdefault(
                "review",
                {
                    **review_decision,
                    "iterations": review_runs,
                    "convergence": "approved" if review_decision.get("approved") else "not_reviewed",
                },
            )
            response["trace_id"] = trace_id
            response["generated_at"] = datetime.now(UTC).isoformat()
            self._emit(trace, "graph", "completed", {"trace_id": trace_id})
            return GraphRunResult(
                trace_id=trace_id,
                success=True,
                output=response,
                trace=trace.to_list(),
            )
        except GraphError as exc:
            self._emit(
                trace,
                "graph",
                "failed",
                {"reason_code": exc.reason_code, "message": exc.message},
            )
            return GraphRunResult(
                trace_id=trace_id,
                success=False,
                output=None,
                trace=trace.to_list(),
                error={
                    "reason_code": exc.reason_code,
                    "message": exc.message,
                    "alternatives": " | ".join(exc.alternatives),
                },
            )

    async def _execute_node(
        self,
        node: GraphNode,
        inputs: dict[str, Any],
        context: NodeContext,
    ) -> dict[str, Any]:
        if node.node_type == "input.text":
            return {"text": context.input_text}
        if node.node_type == "input.attachment":
            return {"attachment": context.attachments}
        if node.node_type == "filter.context":
            maximum = int(node.config.get("max_characters", 24000))
            text_value = inputs.get("text", context.input_text)
            if isinstance(text_value, dict):
                text_value = json.dumps(text_value, ensure_ascii=False)
            limited = str(text_value)[:maximum]
            return {"text": limited, "context": {"text": limited}}
        if node.node_type == "hardware.profile":
            hardware = detect_hardware()
            preferred = node.config.get("profile", "auto")
            report = build_compatibility_report(
                hardware,
                ResourceRequirements(min_context_tokens=512),
                preferred_profile=None if preferred == "auto" else preferred,
                protection_mode=node.config.get("protection_mode", "protected"),
            )
            if not report.activation_allowed or report.budget is None:
                raise GraphError(
                    "HARDWARE_PROTECTED",
                    report.user_message,
                    report.recommendations,
                )
            return {"budget": report.budget, "report": report}
        if node.node_type == "merge.outputs":
            review = inputs.get("review")
            if isinstance(review, dict):
                review = dict(review)
                review.setdefault("iterations", 1)
            return {
                "result": {
                    "code": inputs.get("code"),
                    "explanation": inputs.get("explanation"),
                    "image": inputs.get("image"),
                    "review": review or {
                        "approved": False,
                        "notes": "Nenhuma revisão foi executada.",
                        "iterations": 0,
                        "convergence": "not_reviewed",
                    },
                }
            }
        if node.node_type == "output.response":
            return {"response": inputs.get("result", {})}
        if node.node_type == "output.trace":
            return {"trace": {"trace_id": context.trace_id}}

        handler = self.handlers.get(node.node_type)
        if handler is not None:
            return await handler(node, inputs, context)
        if context.dry_run and node.node_type.startswith("specialist."):
            return self._dry_run_specialist(node, inputs, context)
        raise GraphError(
            "ENGINE_UNAVAILABLE",
            f"Não há backend registrado para o nó '{node.label}' ({node.config.get('engine', 'n/a')}).",
            ("Instale/configure um backend compatível ou marque o nó como opcional.",),
        )

    @staticmethod
    def _dry_run_specialist(
        node: GraphNode,
        inputs: dict[str, Any],
        context: NodeContext,
    ) -> dict[str, Any]:
        marker = f"[DRY-RUN · {node.config.get('model_id', node.node_type)}]"
        if node.node_type == "specialist.code":
            code = f"# Simulação NeuralMap\n# Entrada: {inputs.get('text', context.input_text)}\n"
            return {"code": code, "text": code}
        if node.node_type == "specialist.chat":
            return {
                "explanation": f"{marker} Explicação simulada da solução solicitada.",
                "text": f"{marker} Explicação simulada.",
            }
        if node.node_type == "specialist.image":
            return {
                "image": {
                    "artifact_id": f"dry-run-{context.trace_id}",
                    "mime_type": "image/png",
                    "status": "not_generated",
                }
            }
        if node.node_type == "specialist.review":
            return {
                "decision": {
                    "approved": True,
                    "score": 1.0,
                    "notes": "Aprovação simulada; nenhum modelo foi chamado.",
                    "feedback": "",
                    "retry_targets": [],
                }
            }
        return {}

    @staticmethod
    def _empty_optional_output(node: GraphNode) -> dict[str, Any]:
        empty: dict[str, Any] = {}
        for port in NODE_SPECS[node.node_type].outputs:
            empty[port] = None
        if node.node_type == "specialist.image":
            empty["image"] = None
        return empty

    @staticmethod
    def _incoming(edges: list[GraphEdge], target: str) -> list[GraphEdge]:
        return [edge for edge in edges if edge.target == target]

    @staticmethod
    def _collect_inputs(
        edges: list[GraphEdge],
        outputs: dict[str, dict[str, Any]],
        outcomes: dict[str, bool],
        *,
        target_node: str,
        include_loop_edges: bool,
    ) -> dict[str, Any]:
        collected: dict[str, Any] = {}
        for edge in edges:
            if edge.source not in outputs:
                continue
            if edge.source_port == "repeat":
                if not include_loop_edges:
                    continue
                repeat_payload = outputs[edge.source].get("repeat")
                if isinstance(repeat_payload, dict):
                    targets = repeat_payload.get("targets", [])
                    if target_node not in targets:
                        continue
            outcome = outcomes.get(edge.source, True)
            if edge.edge_type is EdgeType.ON_SUCCESS and not outcome:
                continue
            if edge.edge_type is EdgeType.ON_FAILURE and outcome:
                continue
            value = outputs[edge.source].get(edge.source_port)
            if edge.source_port not in outputs[edge.source]:
                continue
            if edge.target_port in collected:
                current = collected[edge.target_port]
                if not isinstance(current, list):
                    current = [current]
                current.append(value)
                collected[edge.target_port] = current
            else:
                collected[edge.target_port] = value
        return collected

    @staticmethod
    def _validate_outputs(node: GraphNode, outputs: dict[str, Any]) -> None:
        unknown = set(outputs) - set(NODE_SPECS[node.node_type].outputs)
        if unknown:
            raise GraphError(
                "UNKNOWN_NODE_OUTPUT",
                f"O nó '{node.label}' produziu portas não declaradas: {', '.join(sorted(unknown))}.",
            )

    @staticmethod
    def _normalize_review(
        outputs: dict[str, Any],
        graph: WorkflowGraph,
    ) -> dict[str, Any]:
        decision = outputs.get("decision")
        if decision is None:
            decision = {
                "approved": outputs.get("approved"),
                "feedback": outputs.get("feedback", ""),
                "retry_targets": outputs.get("retry_targets", []),
                "score": outputs.get("score"),
                "notes": outputs.get("notes", ""),
            }
        if not isinstance(decision, dict) or not isinstance(decision.get("approved"), bool):
            raise GraphError(
                "INVALID_REVIEW_DECISION",
                "O revisor precisa retornar decision.approved como booleano.",
                ("Exija JSON estruturado com approved, feedback, retry_targets e notes.",),
            )
        score = decision.get("score")
        if score is not None and (
            isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1
        ):
            raise GraphError(
                "INVALID_REVIEW_SCORE",
                "A nota de revisão deve estar entre 0 e 1.",
            )
        targets = decision.get("retry_targets", [])
        if not isinstance(targets, list) or any(not isinstance(item, str) for item in targets):
            raise GraphError(
                "INVALID_RETRY_TARGETS",
                "retry_targets deve ser uma lista de IDs de especialistas.",
            )
        known = {node.node_id: node for node in graph.nodes}
        loop = next((node for node in graph.nodes if node.node_type == "control.loop"), None)
        allowed = {
            edge.target for edge in graph.edges
            if loop and edge.source == loop.node_id and edge.source_port == "repeat"
        }
        unknown = set(targets) - allowed
        if unknown:
            raise GraphError(
                "INVALID_RETRY_TARGET",
                "A revisão solicitou nós que não estão conectados ao loop: "
                + ", ".join(sorted(unknown)),
            )
        if any(target not in known or not known[target].node_type.startswith("specialist.") for target in targets):
            raise GraphError("INVALID_RETRY_TARGET", "retry_targets pode apontar somente para especialistas.")
        return {
            "approved": decision["approved"],
            "feedback": str(decision.get("feedback", "")),
            "retry_targets": targets,
            "score": float(score) if score is not None else None,
            "notes": str(decision.get("notes", "")),
        }

    @staticmethod
    def _resolve_retry_targets(
        graph: WorkflowGraph,
        loop_node: GraphNode,
        requested: list[str] | Any,
    ) -> list[str]:
        connected = [
            edge.target for edge in graph.edges
            if edge.source == loop_node.node_id and edge.source_port == "repeat"
        ]
        aliases = {
            node.node_id: node.node_id for node in graph.nodes
        }
        selected: list[str] = []
        if not isinstance(requested, list):
            raise GraphError("INVALID_RETRY_TARGETS", "retry_targets precisa ser uma lista.")
        for item in requested:
            target = aliases.get(item)
            if target is None:
                target = next(
                    (
                        node.node_id for node in graph.nodes
                        if node.node_type == f"specialist.{item}"
                    ),
                    None,
                )
            if target in connected and target not in selected:
                selected.append(target)
        return selected

    @staticmethod
    def _affected_nodes(
        graph: WorkflowGraph,
        start_nodes: list[str],
        *,
        stop_at: set[str],
    ) -> set[str]:
        node_map = {node.node_id: node for node in graph.nodes}
        adjacency: dict[str, list[str]] = {}
        for edge in graph.edges:
            if edge.source_port == "repeat":
                continue
            adjacency.setdefault(edge.source, []).append(edge.target)
        affected = set(start_nodes)
        queue = list(start_nodes)
        while queue:
            current = queue.pop(0)
            for target in adjacency.get(current, []):
                if target in affected:
                    continue
                if node_map[target].node_type in stop_at:
                    if node_map[target].node_type == "control.loop":
                        affected.add(target)
                    continue
                affected.add(target)
                queue.append(target)
        loop = next(
            (node for node in graph.nodes if node.node_type == "control.loop"),
            None,
        )
        if loop:
            affected.add(loop.node_id)
        return affected

    @staticmethod
    def _check_cancel(event: asyncio.Event, node_id: str) -> None:
        if event.is_set():
            raise GraphError(
                "EXECUTION_CANCELLED",
                f"Execução cancelada antes do nó '{node_id}'.",
            )

    def _emit(
        self,
        trace: ExecutionTrace,
        stage: str,
        status: str,
        details: dict[str, Any],
    ) -> None:
        event = trace.add(stage, status, details)
        if self.on_event is not None:
            self.on_event(stage, status, event.details)
