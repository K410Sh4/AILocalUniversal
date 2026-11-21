"""Reconciliação e capacidade de reutilização de modelos residentes.

Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from engines.base import RunningModelSnapshot
from model_hub.contracts import ModelArtifact, ModelRecord


class ResidencyStatus(StrEnum):
    """Estado de identidade que pode ser provado pelos metadados disponíveis."""

    CONFIRMED = "confirmed"
    DIGEST_MISSING = "digest_missing"
    DIGEST_MISMATCH = "digest_mismatch"
    AMBIGUOUS = "ambiguous"
    NOT_RESIDENT = "not_resident"
    ARTIFACT_MISSING = "artifact_missing"


class ResidentCapacityStatus(StrEnum):
    """Resultado da avaliação de reutilização da capacidade já carregada."""

    REUSE_READY = "reuse_ready"
    IDENTITY_UNVERIFIED = "identity_unverified"
    TELEMETRY_INCOMPLETE = "telemetry_incomplete"
    CONTEXT_REQUIRES_RELOAD = "context_requires_reload"
    MODEL_CONTEXT_EXCEEDED = "model_context_exceeded"
    CONCURRENCY_UNVERIFIED = "concurrency_unverified"


@dataclass(frozen=True, slots=True)
class ModelResidency:
    """Resultado de identidade; não representa uma estimativa de memória."""

    model_id: str
    status: ResidencyStatus
    artifact_reference: str | None
    resident_name: str | None
    artifact_digest: str | None
    resident_digest: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class ResidentCapacityAssessment:
    """Capacidade de runner que pode ser reutilizada sem novo carregamento.

    incremental_runner_bytes=0 significa apenas que o runner já alocou os
    pesos, o contexto configurado e seus buffers reportados. Não representa
    memória total do processo, nem promete custo zero para o sistema.
    """

    model_id: str
    status: ResidentCapacityStatus
    residency: ModelResidency
    requested_context_tokens: int
    concurrent_requests: int
    resident_total_bytes: int | None
    resident_vram_bytes: int | None
    resident_context_capacity_tokens: int | None
    incremental_runner_bytes: int | None
    reason: str


def reconcile_model_residency(
    record: ModelRecord,
    snapshots: list[RunningModelSnapshot],
    *,
    runtime: str = "ollama",
) -> ModelResidency:
    """Confirma residência somente com referência e digest correspondentes.

    Nomes/tags sem digest nunca autorizam tratar o custo de pesos como zero.
    O resultado é apenas identidade observada; não infere RAM, VRAM ou KV.
    """
    artifacts = [
        item
        for item in record.artifacts
        if item.runtime.casefold() == runtime.casefold() and item.installed
    ]
    if not artifacts:
        return ModelResidency(
            model_id=record.record_id,
            status=ResidencyStatus.ARTIFACT_MISSING,
            artifact_reference=None,
            resident_name=None,
            artifact_digest=None,
            resident_digest=None,
            reason="Não há artefato instalado correspondente ao runtime consultado.",
        )

    candidates: list[tuple[ModelArtifact, RunningModelSnapshot]] = []
    for artifact in artifacts:
        reference = artifact.reference.casefold()
        for snapshot in snapshots:
            names = {snapshot.name.casefold()}
            if snapshot.model:
                names.add(snapshot.model.casefold())
            if reference in names:
                candidates.append((artifact, snapshot))

    if not candidates:
        artifact = artifacts[0]
        return ModelResidency(
            model_id=record.record_id,
            status=ResidencyStatus.NOT_RESIDENT,
            artifact_reference=artifact.reference,
            resident_name=None,
            artifact_digest=artifact.digest,
            resident_digest=None,
            reason="Nenhum modelo residente corresponde à referência instalada.",
        )

    if len(candidates) != 1:
        return ModelResidency(
            model_id=record.record_id,
            status=ResidencyStatus.AMBIGUOUS,
            artifact_reference=None,
            resident_name=None,
            artifact_digest=None,
            resident_digest=None,
            reason="Mais de uma combinação de artefato/modelo residente corresponde à referência.",
        )

    artifact, snapshot = candidates[0]
    artifact_digest = artifact.digest.strip() if artifact.digest else None
    resident_digest = snapshot.digest.strip() if snapshot.digest else None
    if not artifact_digest or not resident_digest:
        status = ResidencyStatus.DIGEST_MISSING
        reason = "Referência coincide, mas falta digest em um dos lados; residência não comprovada."
    elif artifact_digest.casefold() != resident_digest.casefold():
        status = ResidencyStatus.DIGEST_MISMATCH
        reason = "O digest residente diverge do artefato instalado; identidade não comprovada."
    else:
        status = ResidencyStatus.CONFIRMED
        reason = (
            "Referência e digest coincidem; identidade residente confirmada. "
            "Nenhuma dedução de memória foi aplicada."
        )

    return ModelResidency(
        model_id=record.record_id,
        status=status,
        artifact_reference=artifact.reference,
        resident_name=snapshot.name,
        artifact_digest=artifact_digest,
        resident_digest=resident_digest,
        reason=reason,
    )


def assess_resident_capacity(
    record: ModelRecord,
    snapshots: list[RunningModelSnapshot],
    *,
    context_tokens: int,
    concurrent_requests: int = 1,
    runtime: str = "ollama",
) -> ResidentCapacityAssessment:
    """Avalia se um runner residente pode atender uma tarefa sem novo load.

    O caminho rápido exige identidade por digest, footprint reportado válido,
    contexto já configurado suficiente e uma única solicitação concorrente.
    Contexto e buffers do runner já carregado não são somados novamente à
    memória livre do sistema. Sem qualquer uma dessas provas, o chamador deve
    voltar ao estimador frio.
    """
    for value, name in (
        (context_tokens, "context_tokens"),
        (concurrent_requests, "concurrent_requests"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} precisa ser um inteiro positivo.")

    residency = reconcile_model_residency(record, snapshots, runtime=runtime)

    def result(
        status: ResidentCapacityStatus,
        reason: str,
        *,
        snapshot: RunningModelSnapshot | None = None,
        incremental: int | None = None,
    ) -> ResidentCapacityAssessment:
        return ResidentCapacityAssessment(
            model_id=record.record_id,
            status=status,
            residency=residency,
            requested_context_tokens=context_tokens,
            concurrent_requests=concurrent_requests,
            resident_total_bytes=snapshot.size_bytes if snapshot else None,
            resident_vram_bytes=snapshot.size_vram_bytes if snapshot else None,
            resident_context_capacity_tokens=(
                snapshot.context_length if snapshot else None
            ),
            incremental_runner_bytes=incremental,
            reason=reason,
        )

    if residency.status is not ResidencyStatus.CONFIRMED:
        return result(
            ResidentCapacityStatus.IDENTITY_UNVERIFIED,
            "Identidade por digest não confirmada; usar estimativa de carregamento frio.",
        )

    snapshot = next(
        (
            item
            for item in snapshots
            if item.name == residency.resident_name
            and item.digest
            and residency.resident_digest
            and item.digest.casefold() == residency.resident_digest.casefold()
        ),
        None,
    )
    if snapshot is None:
        return result(
            ResidentCapacityStatus.IDENTITY_UNVERIFIED,
            "Snapshot correspondente não pôde ser recuperado sem ambiguidade.",
        )

    if (
        snapshot.size_bytes is None
        or snapshot.size_bytes <= 0
        or snapshot.size_vram_bytes is None
        or snapshot.size_vram_bytes > snapshot.size_bytes
        or snapshot.context_length is None
        or snapshot.context_length <= 0
    ):
        return result(
            ResidentCapacityStatus.TELEMETRY_INCOMPLETE,
            "Tamanho total, VRAM ou capacidade de contexto do runner é ausente ou inconsistente.",
            snapshot=snapshot,
        )

    if concurrent_requests != 1:
        return result(
            ResidentCapacityStatus.CONCURRENCY_UNVERIFIED,
            (\n                "A capacidade de slots concorrentes não está confirmada; "
                "usar estimativa fria/conservadora."
            ),
            snapshot=snapshot,
        )

    if (
        record.context_window is not None
        and context_tokens > record.context_window
    ):
        return result(
            ResidentCapacityStatus.MODEL_CONTEXT_EXCEEDED,
            "O contexto solicitado excede a janela declarada do modelo.",
            snapshot=snapshot,
        )

    if context_tokens > snapshot.context_length:
        return result(
            ResidentCapacityStatus.CONTEXT_REQUIRES_RELOAD,
            (\n                "O runner residente não foi configurado para o contexto solicitado; "
                "será necessário recarregar."
            ),
            snapshot=snapshot,
        )

    return result(
        ResidentCapacityStatus.REUSE_READY,
        (
            "Identidade, footprint reportado e capacidade do runner confirmados. "
            "Para uma solicitação dentro do contexto já alocado, pesos, KV e "
            "buffers do runner não são contabilizados novamente. O custo de "
            "memória externo ao runner continua sujeito à margem global."
        ),
        snapshot=snapshot,
        incremental=0,
    )
