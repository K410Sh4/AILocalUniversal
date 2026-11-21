"""Reconciliação conservadora entre artefatos instalados e modelos residentes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from engines.base import RunningModelSnapshot
from model_hub.contracts import ModelRecord


class ResidencyStatus(StrEnum):
    """Estado de residência que pode ser provado pelos metadados disponíveis."""

    CONFIRMED = "confirmed"
    DIGEST_MISSING = "digest_missing"
    DIGEST_MISMATCH = "digest_mismatch"
    AMBIGUOUS = "ambiguous"
    NOT_RESIDENT = "not_resident"
    ARTIFACT_MISSING = "artifact_missing"


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

    candidates: list[tuple[object, RunningModelSnapshot]] = []
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
