"""Deterministic scoring for normalized investigation outcomes."""

from __future__ import annotations

from .models import EvaluationCase, EvaluationOutcome, EvaluationReport, ScenarioScore
from .diagnosis import diagnosis_status as classify_diagnosis


def score_outcome(case: EvaluationCase, outcome: EvaluationOutcome) -> ScenarioScore:
    """Score one outcome using only its trace and evaluation-only expectation."""
    if case.scenario_id != outcome.scenario_id:
        raise ValueError("Evaluation case and outcome scenario IDs must match.")

    report = outcome.final_report
    evidence_ids = {item.evidence_id for item in report.deterministic_evidence}
    cause = report.likely_cause.statement.lower() if report.likely_cause else ""
    diagnosis_status = classify_diagnosis(case, cause)
    root_cause_match = diagnosis_status == "correct"
    required_evidence_present = set(case.required_evidence_ids) <= evidence_ids
    citations_valid = _citations_valid(outcome)
    hypothesis_trace_valid = _hypothesis_trace_valid(outcome)
    false_positive = diagnosis_status == "incorrect"
    reasons = _reasons(
        case,
        outcome,
        root_cause_match,
        diagnosis_status,
        required_evidence_present,
        citations_valid,
        hypothesis_trace_valid,
        false_positive,
    )
    return ScenarioScore(
        scenario_id=outcome.scenario_id,
        candidate_name=outcome.candidate_name,
        root_cause_match=root_cause_match,
        diagnosis_status=diagnosis_status,
        required_evidence_present=required_evidence_present,
        citations_valid=citations_valid,
        hypothesis_trace_valid=hypothesis_trace_valid,
        false_positive=false_positive,
        additional_actions=len(report.actions_taken),
        tool_call_count=outcome.tool_call_count,
        termination_reason=report.termination_reason,
        reasons=reasons,
    )


def build_evaluation_report(outcomes: list[EvaluationOutcome], cases: list[EvaluationCase]) -> EvaluationReport:
    """Score one named candidate over the complete local suite."""
    if not outcomes:
        raise ValueError("At least one evaluation outcome is required.")
    candidate_names = {outcome.candidate_name for outcome in outcomes}
    if len(candidate_names) != 1:
        raise ValueError("An evaluation report must contain one candidate name.")
    cases_by_id = {case.scenario_id: case for case in cases}
    if set(outcome.scenario_id for outcome in outcomes) != set(cases_by_id):
        raise ValueError("Outcomes must cover each evaluation case exactly once.")
    scores = [score_outcome(cases_by_id[outcome.scenario_id], outcome) for outcome in outcomes]
    total = len(scores)
    aggregate = {
        "scenario_count": total,
        "root_cause_match_rate": _rate(sum(score.root_cause_match for score in scores), total),
        "required_evidence_rate": _rate(sum(score.required_evidence_present for score in scores), total),
        "citation_validity_rate": _rate(sum(score.citations_valid for score in scores), total),
        "hypothesis_trace_validity_rate": _rate(sum(score.hypothesis_trace_valid for score in scores), total),
        "false_positive_count": sum(score.false_positive for score in scores),
        "ambiguous_diagnosis_count": sum(score.diagnosis_status == "ambiguous" for score in scores),
        "no_diagnosis_count": sum(score.diagnosis_status == "no_diagnosis" for score in scores),
        "incorrect_diagnosis_count": sum(score.diagnosis_status == "incorrect" for score in scores),
        "mean_additional_actions": _rate(sum(score.additional_actions for score in scores), total),
        "mean_tool_calls": _rate(sum(score.tool_call_count for score in scores), total),
    }
    return EvaluationReport(
        candidate_name=next(iter(candidate_names)),
        scores=scores,
        aggregate=aggregate,
        limitations=[
            "This three-scenario synthetic suite measures local behavior only; it does not establish production performance.",
            "Root-cause matching uses accepted keywords rather than semantic judging.",
        ],
    )


def _citations_valid(outcome: EvaluationOutcome) -> bool:
    evidence_ids = {item.evidence_id for item in outcome.final_report.deterministic_evidence}
    claims = [outcome.final_report.likely_cause, outcome.final_report.impact, *outcome.final_report.findings]
    for claim in claims:
        if claim is not None and (not claim.evidence_ids or not set(claim.evidence_ids) <= evidence_ids):
            return False
    for hypothesis in outcome.final_report.hypotheses:
        cited = set(hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids)
        if not cited <= evidence_ids:
            return False
    return True


def _hypothesis_trace_valid(outcome: EvaluationOutcome) -> bool:
    hypotheses = outcome.final_report.hypotheses
    if len(hypotheses) < 2 or len({hypothesis.hypothesis_id for hypothesis in hypotheses}) != len(hypotheses):
        return False
    return all(
        hypothesis.status not in {"supported", "rejected"}
        or bool(hypothesis.supporting_evidence_ids if hypothesis.status == "supported" else hypothesis.contradicting_evidence_ids)
        for hypothesis in hypotheses
    )


def _reasons(
    case: EvaluationCase,
    outcome: EvaluationOutcome,
    root_cause_match: bool,
    diagnosis_status: str,
    required_evidence_present: bool,
    citations_valid: bool,
    hypothesis_trace_valid: bool,
    false_positive: bool,
) -> list[str]:
    reasons: list[str] = []
    if diagnosis_status == "no_diagnosis":
        reasons.append("The report did not make a root-cause diagnosis.")
    elif diagnosis_status == "ambiguous":
        reasons.append("The report made an allowed but less-specific diagnosis.")
    elif not root_cause_match:
        reasons.append(f"Likely cause did not match accepted keywords for {case.root_cause_label}.")
    if not required_evidence_present:
        missing = sorted(set(case.required_evidence_ids) - {item.evidence_id for item in outcome.final_report.deterministic_evidence})
        reasons.append(f"Missing required evidence IDs: {', '.join(missing)}.")
    if not citations_valid:
        reasons.append("A retained claim or hypothesis cited evidence absent from the trace.")
    if not hypothesis_trace_valid:
        reasons.append("The trace did not contain two valid, distinct hypotheses.")
    if false_positive:
        reasons.append("The report asserted an unsupported root cause.")
    if not reasons:
        reasons.append("All deterministic checks passed.")
    return reasons


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
