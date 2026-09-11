"""A small deterministic baseline using only public Phase 2 evidence."""

from __future__ import annotations

from investigator.agent.nodes import gather_initial_evidence
from investigator.agent.state import EvidenceBackedClaim, FinalReport, IncidentInput

from .models import EvaluationOutcome


STATIC_RULES_CANDIDATE = "static_rules"


def run_static_rules(*, scenario_id: str, incident: IncidentInput) -> EvaluationOutcome:
    """Apply transparent scenario-agnostic rules to the fixed evidence bundle."""
    gathered = gather_initial_evidence({"incident": incident})
    evidence = gathered["evidence"]
    evidence_by_id = {item.evidence_id: item for item in evidence}
    cause = _select_cause(evidence_by_id)
    report = FinalReport(
        incident_id=incident.incident_id,
        summary="Static-rule baseline over the public deterministic evidence bundle.",
        likely_cause=cause,
        limitations=[
            "This baseline uses fixed rules and does not generate or evaluate competing hypotheses.",
        ],
        deterministic_evidence=evidence,
        termination_reason="baseline_completed",
    )
    return EvaluationOutcome(
        scenario_id=scenario_id,
        candidate_name=STATIC_RULES_CANDIDATE,
        final_report=report,
        tool_call_count=len(gathered["tools_used"]),
    )


def _select_cause(evidence_by_id: dict[str, object]) -> EvidenceBackedClaim | None:
    source_comparison = evidence_by_id.get("E02")
    source_profile = evidence_by_id.get("E04")
    metadata = evidence_by_id.get("E05")
    if source_comparison is None or source_profile is None or metadata is None:
        return None

    distribution_changes = source_comparison.data.get("categorical_distribution_changes", {})
    status_changes = distribution_changes.get("order_status", {})
    filter_value = metadata.data.get("filter", {}).get("equals")
    if status_changes.get("COMPLETE", {}).get("incident_count", 0) and filter_value == "completed":
        return EvidenceBackedClaim(
            statement="An order_status enum value changed while the transformation filter remained completed.",
            evidence_ids=["E02", "E05"],
        )

    amount_profile = source_profile.data.get("columns", {}).get("amount", {})
    if amount_profile.get("null_count", 0) and "amount" in metadata.data.get("required_fields", []):
        return EvidenceBackedClaim(
            statement="Null amount values increased and violated the transformation's required amount field.",
            evidence_ids=["E04", "E05"],
        )

    row_count = source_comparison.data.get("row_count", {})
    if row_count.get("delta", 0) < 0 and metadata.data.get("partitioning"):
        return EvidenceBackedClaim(
            statement="A source partition was unavailable, leaving ingestion and downstream volume incomplete.",
            evidence_ids=["E02", "E05"],
        )
    return None
