"""Evidence-citation validation and safe final-report construction."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from investigator.agent.state import (
    AnalysisResult,
    EvidenceBackedClaim,
    FinalReport,
    IncidentInput,
)


def claim_has_valid_citations(
    claim: EvidenceBackedClaim,
    available_evidence_ids: set[str],
) -> bool:
    """Return whether every citation in a claim exists in gathered evidence."""
    return bool(claim.evidence_ids) and all(
        evidence_id in available_evidence_ids for evidence_id in claim.evidence_ids
    )


def build_final_report(
    *,
    incident: IncidentInput,
    analysis: AnalysisResult | None,
    available_evidence_ids: set[str],
    prior_errors: Sequence[str],
) -> tuple[FinalReport, list[str]]:
    """Build a report while omitting claims with unknown evidence citations."""
    limitations = list(prior_errors)
    validation_errors: list[str] = []

    if analysis is None:
        limitations.append("No analysis result was available; no diagnosis was produced.")
        return (
            FinalReport(
                incident_id=incident.incident_id,
                summary=(
                    f"Partial investigation report for {incident.incident_id}: "
                    "analysis was unavailable."
                ),
                limitations=limitations,
            ),
            validation_errors,
        )

    limitations.extend(analysis.limitations)
    findings = _valid_claims(
        analysis.observations,
        "observation",
        available_evidence_ids,
        limitations,
        validation_errors,
    )
    likely_cause = _valid_optional_claim(
        analysis.likely_cause,
        "likely cause",
        available_evidence_ids,
        limitations,
        validation_errors,
    )
    impact = _valid_optional_claim(
        analysis.impact,
        "impact",
        available_evidence_ids,
        limitations,
        validation_errors,
    )
    if likely_cause is not None or impact is not None:
        limitations.append(
            "Likely cause and impact are LLM-generated inferences constrained by cited evidence."
        )

    return (
        FinalReport(
            incident_id=incident.incident_id,
            summary=(
                f"LLM-assisted investigation report for {incident.incident_id}: "
                f"{len(findings)} evidence-backed finding(s) retained."
            ),
            findings=findings,
            likely_cause=likely_cause,
            impact=impact,
            limitations=limitations,
            recommended_next_action=analysis.recommended_next_action,
        ),
        validation_errors,
    )


def _valid_claims(
    claims: Iterable[EvidenceBackedClaim],
    label: str,
    available_evidence_ids: set[str],
    limitations: list[str],
    validation_errors: list[str],
) -> list[EvidenceBackedClaim]:
    return [
        claim
        for claim in claims
        if _retain_claim(
            claim, label, available_evidence_ids, limitations, validation_errors
        )
    ]


def _valid_optional_claim(
    claim: EvidenceBackedClaim | None,
    label: str,
    available_evidence_ids: set[str],
    limitations: list[str],
    validation_errors: list[str],
) -> EvidenceBackedClaim | None:
    if claim is None:
        return None
    return (
        claim
        if _retain_claim(
            claim, label, available_evidence_ids, limitations, validation_errors
        )
        else None
    )


def _retain_claim(
    claim: EvidenceBackedClaim,
    label: str,
    available_evidence_ids: set[str],
    limitations: list[str],
    validation_errors: list[str],
) -> bool:
    if claim_has_valid_citations(claim, available_evidence_ids):
        return True

    unknown_ids = sorted(set(claim.evidence_ids) - available_evidence_ids)
    message = f"Omitted {label} with unknown evidence IDs: {', '.join(unknown_ids)}."
    limitations.append(message)
    validation_errors.append(message)
    return False
