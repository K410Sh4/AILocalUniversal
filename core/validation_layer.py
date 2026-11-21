"""Validação estrutural e determinística de resultados cognitivos."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from core.cognitive_task import CognitiveTask
from core.deterministic_tools import DeterministicToolRegistry


class ValidationLayer:
    """Valida estrutura, dependências e resultados reproduzíveis localmente.

    Conteúdo produzido por LLM nunca é marcado como factualmente verificado por
    esta camada. Sem fontes ou validadores de domínio, ele exige revisão.
    """

    def __init__(self, tools: DeterministicToolRegistry | None = None) -> None:
        self.tools = tools or DeterministicToolRegistry()

    @staticmethod
    def _check(
        name: str,
        passed: bool,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "failed",
            "message": message,
            "details": details or {},
        }

    @staticmethod
    def _issue(
        code: str,
        severity: str,
        message: str,
        subtask_id: str | None = None,
    ) -> dict[str, Any]:
        item = {"code": code, "severity": severity, "message": message}
        if subtask_id is not None:
            item["subtask_id"] = subtask_id
        return item

    @staticmethod
    def _report(
        checks: list[dict[str, Any]],
        issues: list[dict[str, Any]],
        factual_status: str,
        checked_subtasks: int = 0,
        total_subtasks: int = 0,
    ) -> dict[str, Any]:
        failed = sum(check["status"] == "failed" for check in checks)
        warnings = sum(issue["severity"] == "warning" for issue in issues)
        status = "failed" if failed else "needs_review" if warnings else "passed"
        return {
            "status": status,
            "structural_status": "failed" if failed else "passed",
            "factual_status": factual_status,
            "checked_at": datetime.now(UTC).isoformat(),
            "summary": {
                "checks_passed": len(checks) - failed,
                "checks_failed": failed,
                "warnings": warnings,
                "checked_subtasks": checked_subtasks,
                "total_subtasks": total_subtasks,
            },
            "checks": checks,
            "issues": issues,
        }

    @staticmethod
    def _values_match(expected: Any, actual: Any) -> bool:
        if isinstance(expected, bool) or isinstance(actual, bool):
            return expected == actual
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            return math.isclose(float(expected), float(actual), rel_tol=1e-10, abs_tol=1e-12)
        return expected == actual

    def _replay_tool(
        self,
        text: str,
        recorded: dict[str, Any],
        subtask_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        checks: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        replay = self.tools.execute(text)
        if replay is None or not replay.matched:
            checks.append(
                self._check(
                    "deterministic_tool_replay",
                    False,
                    "Não foi possível reproduzir o resultado com a ferramenta local.",
                )
            )
            issues.append(
                self._issue(
                    "deterministic_replay_unavailable",
                    "error",
                    "O resultado não pôde ser reproduzido pela ferramenta local.",
                    subtask_id,
                )
            )
            return checks, issues, False

        checks.append(
            self._check(
                "deterministic_tool_replay",
                True,
                "A ferramenta reconheceu e reproduziu a operação.",
                {"tool": replay.name, "operation_success": replay.success},
            )
        )
        tool_name = recorded.get("tool", recorded.get("name"))
        tool_matches = tool_name == replay.name
        content_matches = recorded.get("content") == replay.content
        success_matches = recorded.get("success") is replay.success
        value_matches = self._values_match(recorded.get("value"), replay.value)
        checks.extend(
            [
                self._check(
                    "deterministic_tool_identity",
                    tool_matches,
                    "Ferramenta registrada corresponde à reprodução."
                    if tool_matches
                    else "Ferramenta registrada diverge da reprodução.",
                    {"recorded": tool_name, "replayed": replay.name},
                ),
                self._check(
                    "deterministic_tool_output",
                    content_matches,
                    "Texto registrado corresponde à reprodução."
                    if content_matches
                    else "Texto registrado diverge da reprodução.",
                    {"recorded": recorded.get("content"), "replayed": replay.content},
                ),
                self._check(
                    "deterministic_tool_outcome",
                    success_matches,
                    "O estado de sucesso/erro registrado corresponde à reprodução."
                    if success_matches
                    else "O estado de sucesso/erro diverge da reprodução.",
                    {"recorded": recorded.get("success"), "replayed": replay.success},
                ),
                self._check(
                    "deterministic_tool_value",
                    value_matches,
                    "Valor registrado corresponde à reprodução."
                    if value_matches
                    else "Valor registrado diverge da reprodução.",
                    {"recorded": recorded.get("value"), "replayed": replay.value},
                ),
            ]
        )
        passed = tool_matches and content_matches and success_matches and value_matches
        if not passed:
            issues.append(
                self._issue(
                    "deterministic_result_mismatch",
                    "error",
                    "O resultado armazenado diverge da reprodução determinística.",
                    subtask_id,
                )
            )
        return checks, issues, passed

    def validate_subtask(
        self,
        task: CognitiveTask,
        subtask: dict[str, Any],
    ) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        subtask_id = str(subtask.get("id", "")) or None
        result = subtask.get("result")
        has_result = isinstance(result, dict) and bool(str(result.get("content", "")).strip())
        checks.append(
            self._check(
                "subtask_result_present",
                has_result,
                "A subtarefa produziu uma saída não vazia."
                if has_result
                else "A subtarefa não produziu uma saída utilizável.",
            )
        )
        if not has_result:
            issues.append(
                self._issue(
                    "subtask_result_missing",
                    "error",
                    "Não existe uma saída utilizável para esta subtarefa.",
                    subtask_id,
                )
            )
            return self._report(checks, issues, "not_verified")

        by_id = {str(item.get("id")): item for item in task.subtask_plan}
        dependencies = subtask.get("depends_on", [])
        deps_valid = isinstance(dependencies, list)
        unresolved: list[str] = []
        if deps_valid:
            for dependency_id in dependencies:
                dependency = by_id.get(str(dependency_id))
                dependency_result = dependency.get("result") if dependency else None
                if (
                    dependency is None
                    or dependency.get("status") != "completed"
                    or not isinstance(dependency_result, dict)
                    or not str(dependency_result.get("content", "")).strip()
                ):
                    deps_valid = False
                    unresolved.append(str(dependency_id))
        checks.append(
            self._check(
                "subtask_dependencies",
                deps_valid,
                "Todas as dependências possuem resultados concluídos."
                if deps_valid
                else "Há dependências ausentes ou não concluídas.",
                {"unresolved": unresolved},
            )
        )
        if not deps_valid:
            issues.append(
                self._issue(
                    "subtask_dependency_unresolved",
                    "error",
                    "A subtarefa depende de resultados ainda não concluídos.",
                    subtask_id,
                )
            )

        factual_status = "not_independently_verified"
        execution_kind = subtask.get("execution_kind")
        if execution_kind == "deterministic_tool":
            replay_checks, replay_issues, replay_passed = self._replay_tool(
                str(subtask.get("text", "")),
                result,
                subtask_id,
            )
            checks.extend(replay_checks)
            issues.extend(replay_issues)
            factual_status = "verified_deterministic" if replay_passed else "failed"
        elif execution_kind == "llm":
            model_present = bool(str(result.get("model", "")).strip())
            checks.append(
                self._check(
                    "llm_model_recorded",
                    model_present,
                    "O modelo utilizado foi registrado."
                    if model_present
                    else "O modelo utilizado não foi identificado.",
                )
            )
            if model_present:
                issues.append(
                    self._issue(
                        "llm_output_not_independently_verified",
                        "warning",
                        "A estrutura foi conferida, mas o conteúdo factual não foi "
                        "verificado por fonte ou ferramenta independente.",
                        subtask_id,
                    )
                )
            else:
                issues.append(
                    self._issue(
                        "llm_model_missing",
                        "error",
                        "A saída não identifica o modelo que a produziu.",
                        subtask_id,
                    )
                )
        else:
            checks.append(
                self._check(
                    "execution_kind_supported",
                    False,
                    "O tipo de execução da subtarefa não é reconhecido.",
                )
            )
            issues.append(
                self._issue(
                    "unknown_execution_kind",
                    "error",
                    f"Tipo de execução não reconhecido: {execution_kind!r}.",
                    subtask_id,
                )
            )
        return self._report(checks, issues, factual_status)


    def progress_report(self, task: CognitiveTask) -> dict[str, Any]:
        """Agrega validações já concluídas enquanto outras subtarefas continuam."""
        reports = [
            item["validation_report"]
            for item in task.subtask_plan
            if isinstance(item.get("validation_report"), dict)
        ]
        checks = [
            dict(check)
            for report in reports
            for check in report.get("checks", [])
        ]
        issues = [
            dict(issue)
            for report in reports
            for issue in report.get("issues", [])
        ]
        failed = any(report.get("status") == "failed" for report in reports)
        return {
            "status": "failed" if failed else "running",
            "structural_status": "failed" if failed else "in_progress",
            "factual_status": "not_independently_verified",
            "checked_at": datetime.now(UTC).isoformat(),
            "summary": {
                "checks_passed": sum(check.get("status") == "passed" for check in checks),
                "checks_failed": sum(check.get("status") == "failed" for check in checks),
                "warnings": sum(issue.get("severity") == "warning" for issue in issues),
                "checked_subtasks": len(reports),
                "total_subtasks": len(task.subtask_plan),
            },
            "checks": checks,
            "issues": issues,
        }

    def validate_deterministic_response(self, task: CognitiveTask) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        result = task.result if isinstance(task.result, dict) else {}
        recorded = task.deterministic_results[-1] if task.deterministic_results else {}
        has_result = bool(str(result.get("content", "")).strip()) and bool(recorded)
        checks.append(
            self._check(
                "deterministic_response_present",
                has_result,
                "Resposta e registro da ferramenta estão presentes."
                if has_result
                else "Resposta ou registro determinístico ausente.",
            )
        )
        if not has_result:
            issues.append(
                self._issue(
                    "deterministic_response_missing",
                    "error",
                    "Não há resultado determinístico completo para validar.",
                )
            )
            return self._report(checks, issues, "not_verified")

        replay_checks, replay_issues, replay_passed = self._replay_tool(
            task.normalized_text or task.original_text,
            recorded,
        )
        checks.extend(replay_checks)
        issues.extend(replay_issues)
        response_matches = all(
            (
                recorded.get("matched") is True,
                result.get("tool") == recorded.get("name"),
                result.get("content") == recorded.get("content"),
                result.get("success") is recorded.get("success"),
                self._values_match(result.get("value"), recorded.get("value")),
            )
        )
        checks.append(
            self._check(
                "deterministic_response_matches_record",
                response_matches,
                "A resposta planejada corresponde ao registro da ferramenta."
                if response_matches
                else "A resposta planejada diverge do registro da ferramenta.",
            )
        )
        if not response_matches:
            issues.append(
                self._issue(
                    "deterministic_response_mismatch",
                    "error",
                    "A resposta que seria exibida não corresponde ao registro determinístico.",
                )
            )
        passed = replay_passed and response_matches
        return self._report(
            checks,
            issues,
            "verified_deterministic" if passed else "failed",
        )

    def validate_chat_response(
        self,
        task: CognitiveTask,
        content: str,
        *,
        completeness_threshold: float = 0.8,
    ) -> dict[str, Any]:
        """Valida presença e requisitos declarados sem atestar a verdade factual.

        A média ponderada não substitui o gate dos itens obrigatórios. Quando a
        tarefa não declara subtarefas, completude fica como not_assessed.
        """
        if (
            isinstance(completeness_threshold, bool)
            or not isinstance(completeness_threshold, (int, float))
            or not math.isfinite(completeness_threshold)
            or not 0.0 <= completeness_threshold <= 1.0
        ):
            raise ValueError("completeness_threshold precisa estar entre 0 e 1.")

        checks: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        answer_present = isinstance(content, str) and bool(content.strip())
        checks.append(
            self._check(
                "answer_present",
                answer_present,
                "A resposta contém texto utilizável."
                if answer_present
                else "A resposta está vazia.",
            )
        )
        if not answer_present:
            issues.append(
                self._issue(
                    "answer_missing",
                    "error",
                    "A resposta final está vazia e não pode ser apresentada.",
                )
            )

        completeness_score: float | None = None
        required_count = 0
        completed_required = 0
        if task.subtask_plan:
            total_weight = 0.0
            completed_weight = 0.0
            invalid_weights: list[str] = []
            for item in task.subtask_plan:
                raw_weight = item.get("weight", 1.0)
                valid_weight = (
                    not isinstance(raw_weight, bool)
                    and isinstance(raw_weight, (int, float))
                    and math.isfinite(raw_weight)
                    and raw_weight > 0
                )
                if not valid_weight:
                    invalid_weights.append(str(item.get("id", "?")))
                    continue

                weight = float(raw_weight)
                total_weight += weight
                result = item.get("result")
                completed = (
                    item.get("status") == "completed"
                    and isinstance(result, dict)
                    and bool(str(result.get("content", "")).strip())
                )
                if completed:
                    completed_weight += weight
                if item.get("required", True):
                    required_count += 1
                    completed_required += int(completed)

            completeness_score = (
                completed_weight / total_weight if total_weight > 0 else 0.0
            )
            all_required_complete = (
                not invalid_weights and completed_required == required_count
            )
            threshold_met = completeness_score >= completeness_threshold
            complete = all_required_complete and threshold_met
            checks.append(
                self._check(
                    "mandatory_requirements_complete",
                    complete,
                    "Todos os requisitos obrigatórios foram atendidos."
                    if complete
                    else "Há requisitos obrigatórios pendentes ou peso inválido.",
                    {
                        "required_count": required_count,
                        "completed_required": completed_required,
                        "weighted_completeness": round(completeness_score, 4),
                        "threshold": float(completeness_threshold),
                        "invalid_weight_subtasks": invalid_weights,
                    },
                )
            )
            if not complete:
                issues.append(
                    self._issue(
                        "mandatory_requirements_incomplete",
                        "error",
                        "A resposta não pode ser considerada completa enquanto houver "
                        "requisitos obrigatórios pendentes.",
                    )
                )
        else:
            checks.append(
                self._check(
                    "mandatory_requirements_complete",
                    True,
                    "Nenhum requisito estruturado foi declarado; completude semântica "
                    "não foi presumida.",
                    {"completeness": "not_assessed"},
                )
            )

        issues.append(
            self._issue(
                "llm_output_not_independently_verified",
                "warning",
                "A Validation Layer conferiu presença e requisitos estruturados, mas não "
                "comprovou a veracidade factual do conteúdo gerado pelo modelo.",
            )
        )
        report = self._report(
            checks,
            issues,
            "not_independently_verified",
            checked_subtasks=completed_required,
            total_subtasks=required_count,
        )
        report["completeness"] = {
            "status": (
                "not_assessed"
                if not task.subtask_plan
                else "passed"
                if all(
                    check["name"] != "mandatory_requirements_complete"
                    or check["status"] == "passed"
                    for check in checks
                )
                else "incomplete"
            ),
            "weighted_score": (
                round(completeness_score, 4)
                if completeness_score is not None
                else None
            ),
            "threshold": float(completeness_threshold),
            "required_count": required_count,
            "completed_required": completed_required,
        }
        return report

    def validate_execution(
        self,
        task: CognitiveTask,
        final_content: str,
    ) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        by_id = {str(item.get("id")): item for item in task.subtask_plan}
        all_complete = bool(task.subtask_plan) and all(
            item.get("status") == "completed"
            and isinstance(item.get("result"), dict)
            and bool(str(item["result"].get("content", "")).strip())
            for item in task.subtask_plan
        )
        checks.append(
            self._check(
                "all_subtasks_completed",
                all_complete,
                "Todas as subtarefas produziram resultados."
                if all_complete
                else "Uma ou mais subtarefas não possuem resultado concluído.",
            )
        )
        if not all_complete:
            issues.append(
                self._issue(
                    "subtask_coverage_incomplete",
                    "error",
                    "A síntese não possui um conjunto completo de resultados intermediários.",
                )
            )

        dependencies_valid = True
        unresolved: list[str] = []
        for item in task.subtask_plan:
            for dependency_id in item.get("depends_on", []):
                dependency = by_id.get(str(dependency_id))
                if dependency is None or dependency.get("status") != "completed":
                    dependencies_valid = False
                    unresolved.append(f"{item.get('id')} -> {dependency_id}")
        checks.append(
            self._check(
                "execution_dependencies",
                dependencies_valid,
                "Todas as dependências foram satisfeitas."
                if dependencies_valid
                else "Existem dependências não satisfeitas.",
                {"unresolved": unresolved},
            )
        )
        if not dependencies_valid:
            issues.append(
                self._issue(
                    "execution_dependency_failure",
                    "error",
                    "A execução contém dependências que não foram concluídas.",
                )
            )

        synthesis_present = bool(final_content.strip())
        checks.append(
            self._check(
                "final_synthesis_present",
                synthesis_present,
                "A síntese final produziu conteúdo."
                if synthesis_present
                else "A síntese final está vazia.",
            )
        )
        if not synthesis_present:
            issues.append(
                self._issue(
                    "final_synthesis_missing",
                    "error",
                    "A execução não produziu uma resposta final utilizável.",
                )
            )

        # A síntese final desta rota é produzida por LLM, mesmo quando todas as
        # subtarefas foram resolvidas por ferramentas determinísticas.
        factual_status = "not_independently_verified"
        checked = 0
        for item in task.subtask_plan:
            report = item.get("validation_report", {})
            passed = report.get("status") in {"passed", "needs_review"}
            checks.append(
                self._check(
                    "subtask_validation",
                    passed,
                    f"Validação da subtarefa {item.get('order', '?')}: "
                    f"{report.get('status', 'ausente')}.",
                    {"subtask_id": item.get("id")},
                )
            )
            checked += int(passed)
            for issue in report.get("issues", []):
                if issue.get("severity") == "warning":
                    issues.append(dict(issue))
            if item.get("execution_kind") == "llm":
                factual_status = "not_independently_verified"

        if factual_status == "not_independently_verified":
            issues.append(
                self._issue(
                    "final_synthesis_not_independently_verified",
                    "warning",
                    "A síntese foi gerada por LLM. A camada conferiu estrutura e fluxo, "
                    "mas não comprova a veracidade factual.",
                )
            )
        return self._report(
            checks,
            issues,
            factual_status,
            checked_subtasks=checked,
            total_subtasks=len(task.subtask_plan),
        )

    @staticmethod
    def interrupted_report(
        status: str,
        message: str,
        subtask_id: str | None = None,
    ) -> dict[str, Any]:
        issue = {
            "code": f"execution_{status}",
            "severity": "error" if status == "failed" else "warning",
            "message": message,
        }
        if subtask_id:
            issue["subtask_id"] = subtask_id
        return {
            "status": status,
            "structural_status": "incomplete",
            "factual_status": "not_independently_verified",
            "checked_at": datetime.now(UTC).isoformat(),
            "summary": {
                "checks_passed": 0,
                "checks_failed": 0,
                "warnings": int(status != "failed"),
                "checked_subtasks": 0,
                "total_subtasks": 0,
            },
            "checks": [],
            "issues": [issue],
        }
