"""Regression tests for the focused Phase 6 hardening changes."""

from __future__ import annotations

from pathlib import Path

from investigator.agent.hypotheses import Hypothesis
from investigator.agent.hypothesis_nodes import generate_hypothesis_report
from investigator.agent.state import EvidenceBackedClaim, EvidenceItem, IncidentInput
from investigator.evaluation.baselines import run_static_rules
from investigator.evaluation.registry import load_evaluation_cases
from investigator.evaluation.scoring import score_outcome


SCENARIOS_ROOT = Path(__file__).resolve().parents[2] / "data" / "scenarios"


def test_scoring_separates_no_diagnosis_from_a_false_positive() -> None:
    case = load_evaluation_cases(SCENARIOS_ROOT)[0]
    outcome = _baseline_outcome("enum_change")
    no_diagnosis = outcome.model_copy(
        update={"final_report": outcome.final_report.model_copy(update={"likely_cause": None})}
    )

    score = score_outcome(case, no_diagnosis)

    assert score.diagnosis_status == "no_diagnosis"
    assert score.root_cause_match is False
    assert score.false_positive is False
    assert "did not make a root-cause diagnosis" in score.reasons[0]


def test_scoring_recognizes_allowed_ambiguous_diagnosis() -> None:
    case = load_evaluation_cases(SCENARIOS_ROOT)[2]
    outcome = _baseline_outcome("missing_partition")
    ambiguous = outcome.model_copy(
        update={
            "final_report": outcome.final_report.model_copy(
                update={
                    "likely_cause": EvidenceBackedClaim(
                        statement="Reduced source volume caused incomplete downstream output.",
                        evidence_ids=["E02"],
                    )
                }
            )
        }
    )

    score = score_outcome(case, ambiguous)

    assert score.diagnosis_status == "ambiguous"
    assert score.false_positive is False
    assert "allowed but less-specific" in score.reasons[0]


def test_unresolved_hypotheses_produce_an_honest_report() -> None:
    scenario_dir = SCENARIOS_ROOT / "null_rate_increase"
    result = generate_hypothesis_report(
        {
            "incident": IncidentInput(
                incident_id="null-rate-unresolved",
                description="Revenue output fell.",
                scenario_dir=str(scenario_dir),
            ),
            "evidence": [
                EvidenceItem(
                    evidence_id="E03",
                    evidence_type="DATA_QUALITY_METRIC",
                    source_tool="compare_distributions",
                    tool_input={},
                    summary="Warehouse output decreased.",
                    data={},
                )
            ],
            "hypotheses": [
                Hypothesis(
                    hypothesis_id="H01",
                    statement="Null values may be responsible.",
                    status="inconclusive",
                    confidence=0.4,
                    rationale="More evidence would be needed.",
                ),
                Hypothesis(
                    hypothesis_id="H02",
                    statement="A load problem may be responsible.",
                    status="inconclusive",
                    confidence=0.2,
                    rationale="More evidence would be needed.",
                ),
            ],
            "actions_taken": [],
            "errors": [],
            "termination_reason": "action_budget_exhausted",
        }
    )

    report = result["final_report"]
    assert result["analysis"] is not None
    assert report.likely_cause is None
    assert "analysis was unavailable" not in report.summary
    assert any("remains unresolved" in limitation for limitation in report.limitations)
    assert report.termination_reason == "action_budget_exhausted"


def _baseline_outcome(scenario_id: str):
    scenario_dir = SCENARIOS_ROOT / scenario_id
    return run_static_rules(
        scenario_id=scenario_id,
        incident=IncidentInput(
            incident_id=f"{scenario_id}-phase-6",
            description="Evaluation fixture.",
            scenario_dir=str(scenario_dir),
        ),
    )
