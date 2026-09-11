"""Reproducible local evaluation runners and JSON output helpers."""

from __future__ import annotations

import json
from pathlib import Path

from investigator.agent.graph import build_investigation_graph
from investigator.agent.state import IncidentInput

from .baselines import STATIC_RULES_CANDIDATE, run_static_rules
from .models import EvaluationOutcome, EvaluationReport
from .registry import SCENARIO_IDS, load_evaluation_cases
from .scoring import build_evaluation_report


INVESTIGATOR_WORKFLOW_CANDIDATE = "investigator_workflow"


def run_evaluation(*, candidate_name: str, scenarios_root: Path) -> EvaluationReport:
    """Run one named candidate across the complete local evaluation suite."""
    cases = load_evaluation_cases(scenarios_root)
    outcomes = [
        _run_candidate(candidate_name, scenario_id, scenarios_root / scenario_id)
        for scenario_id in SCENARIO_IDS
    ]
    return build_evaluation_report(outcomes, cases)


def write_evaluation_report(report: EvaluationReport, output_path: Path) -> None:
    """Write stable JSON to an explicit caller-selected location."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_candidate(candidate_name: str, scenario_id: str, scenario_dir: Path) -> EvaluationOutcome:
    incident = IncidentInput(
        incident_id=f"{scenario_id}-evaluation",
        description=f"Evaluate the {scenario_id} synthetic incident.",
        scenario_dir=str(scenario_dir),
    )
    if candidate_name == STATIC_RULES_CANDIDATE:
        return run_static_rules(scenario_id=scenario_id, incident=incident)
    if candidate_name == INVESTIGATOR_WORKFLOW_CANDIDATE:
        result = build_investigation_graph().invoke({"incident": incident})
        return EvaluationOutcome(
            scenario_id=scenario_id,
            candidate_name=INVESTIGATOR_WORKFLOW_CANDIDATE,
            final_report=result["final_report"],
            tool_call_count=len(result.get("tools_used", [])),
        )
    raise ValueError(f"Unknown evaluation candidate: {candidate_name}.")
