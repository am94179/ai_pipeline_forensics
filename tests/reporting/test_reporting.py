"""Phase 3 Plan 7 tests for citation-validated final reports."""

from __future__ import annotations

from copy import deepcopy

from investigator.agent.state import AnalysisResult, EvidenceBackedClaim, IncidentInput
from investigator.reporting.report import build_final_report, claim_has_valid_citations


def _incident() -> IncidentInput:
    return IncidentInput(
        incident_id="enum-change-2026-09-02",
        description="Revenue-reporting output dropped.",
        scenario_dir="data/scenarios/enum_change",
    )


def test_build_final_report_retains_valid_evidence_backed_claims() -> None:
    analysis = AnalysisResult(
        observations=[
            EvidenceBackedClaim(
                statement="Warehouse output declined.", evidence_ids=["E03"]
            )
        ],
        likely_cause=EvidenceBackedClaim(
            statement="The configured filter excludes the renamed status.", evidence_ids=["E05"]
        ),
        impact=EvidenceBackedClaim(
            statement="Revenue reporting is incomplete.", evidence_ids=["E03"]
        ),
        limitations=["No historical incidents were available."],
        recommended_next_action="Update the transformation filter.",
    )

    report, errors = build_final_report(
        incident=_incident(),
        analysis=analysis,
        available_evidence_ids={"E01", "E03", "E05"},
        prior_errors=[],
    )

    assert errors == []
    assert report.findings == analysis.observations
    assert report.likely_cause == analysis.likely_cause
    assert report.impact == analysis.impact
    assert report.recommended_next_action == "Update the transformation filter."
    assert "LLM-generated inferences" in report.limitations[-1]
    assert claim_has_valid_citations(report.likely_cause, {"E01", "E03", "E05"})


def test_build_final_report_omits_claims_with_unknown_citations_without_mutation() -> None:
    valid_observation = EvidenceBackedClaim(
        statement="Source statuses changed.", evidence_ids=["E02"]
    )
    invalid_observation = EvidenceBackedClaim(
        statement="An unsupported conclusion.", evidence_ids=["E99"]
    )
    analysis = AnalysisResult(
        observations=[valid_observation, invalid_observation],
        likely_cause=EvidenceBackedClaim(
            statement="Unsupported likely cause.", evidence_ids=["E99"]
        ),
        impact=EvidenceBackedClaim(
            statement="Observed impact.", evidence_ids=["E03"]
        ),
    )
    original_analysis = deepcopy(analysis)

    report, errors = build_final_report(
        incident=_incident(),
        analysis=analysis,
        available_evidence_ids={"E02", "E03"},
        prior_errors=[],
    )

    assert report.findings == [valid_observation]
    assert report.likely_cause is None
    assert report.impact == analysis.impact
    assert errors == [
        "Omitted observation with unknown evidence IDs: E99.",
        "Omitted likely cause with unknown evidence IDs: E99.",
    ]
    assert errors == [limitation for limitation in report.limitations if "Omitted" in limitation]
    assert analysis == original_analysis


def test_build_final_report_creates_partial_report_without_analysis() -> None:
    report, errors = build_final_report(
        incident=_incident(),
        analysis=None,
        available_evidence_ids={"E01"},
        prior_errors=["LLM analysis failed (RuntimeError)."],
    )

    assert errors == []
    assert report.findings == []
    assert report.likely_cause is None
    assert report.impact is None
    assert "Partial investigation report" in report.summary
    assert report.limitations == [
        "LLM analysis failed (RuntimeError).",
        "No analysis result was available; no diagnosis was produced.",
    ]
