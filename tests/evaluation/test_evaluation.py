"""Tests for local Phase 5 contracts, scoring, baseline, and runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from investigator.agent.state import EvidenceBackedClaim
from investigator.evaluation.baselines import STATIC_RULES_CANDIDATE, run_static_rules
from investigator.evaluation.models import EvaluationCase, EvaluationOutcome
from investigator.evaluation.registry import load_evaluation_cases
from investigator.evaluation.runner import run_evaluation, write_evaluation_report
from investigator.evaluation.scoring import build_evaluation_report, score_outcome
from investigator.agent.state import IncidentInput


SCENARIOS_ROOT = Path(__file__).resolve().parents[2] / "data" / "scenarios"


def test_registry_loads_three_evaluation_only_contracts() -> None:
    cases = load_evaluation_cases(SCENARIOS_ROOT)

    assert [case.scenario_id for case in cases] == [
        "enum_change",
        "null_rate_increase",
        "missing_partition",
    ]
    assert cases[0].root_cause_label == "enum_value_mismatch"
    assert cases[2].allowed_ambiguity


def test_evaluation_case_rejects_duplicate_or_blank_expectations() -> None:
    with pytest.raises(ValueError, match="distinct"):
        EvaluationCase(
            scenario_id="example",
            root_cause_label="example",
            accepted_keywords=["same", "same"],
            required_evidence_ids=["E01"],
        )
    with pytest.raises(ValueError, match="blank"):
        EvaluationCase(
            scenario_id="example",
            root_cause_label="example",
            accepted_keywords=["cause"],
            required_evidence_ids=[" "],
        )


def test_static_baseline_is_scored_over_all_three_scenarios(tmp_path: Path) -> None:
    report = run_evaluation(candidate_name=STATIC_RULES_CANDIDATE, scenarios_root=SCENARIOS_ROOT)
    output_path = tmp_path / "evaluation.json"
    write_evaluation_report(report, output_path)
    first_bytes = output_path.read_bytes()
    write_evaluation_report(report, output_path)

    assert report.aggregate["scenario_count"] == 3
    assert report.aggregate["root_cause_match_rate"] == 1.0
    assert report.aggregate["required_evidence_rate"] == 1.0
    assert report.aggregate["citation_validity_rate"] == 1.0
    assert report.aggregate["hypothesis_trace_validity_rate"] == 0.0
    assert output_path.read_bytes() == first_bytes
    assert json.loads(output_path.read_text(encoding="utf-8"))["candidate_name"] == STATIC_RULES_CANDIDATE


def test_scoring_flags_wrong_causes_and_invalid_citations() -> None:
    case = load_evaluation_cases(SCENARIOS_ROOT)[0]
    outcome = _baseline_outcome("enum_change")
    invalid_report = outcome.final_report.model_copy(
        update={
            "likely_cause": EvidenceBackedClaim(
                statement="A database outage caused the incident.", evidence_ids=["E99"]
            )
        }
    )
    invalid_outcome = outcome.model_copy(update={"final_report": invalid_report})

    score = score_outcome(case, invalid_outcome)

    assert score.root_cause_match is False
    assert score.citations_valid is False
    assert score.false_positive is True
    assert any("unsupported root cause" in reason for reason in score.reasons)


def test_report_requires_exactly_one_outcome_per_case() -> None:
    cases = load_evaluation_cases(SCENARIOS_ROOT)
    with pytest.raises(ValueError, match="cover each evaluation case"):
        build_evaluation_report([_baseline_outcome("enum_change")], cases)


def _baseline_outcome(scenario_id: str) -> EvaluationOutcome:
    scenario_dir = SCENARIOS_ROOT / scenario_id
    incident = IncidentInput(
        incident_id=f"{scenario_id}-test",
        description="Evaluation fixture.",
        scenario_dir=str(scenario_dir),
    )
    return run_static_rules(scenario_id=scenario_id, incident=incident)
