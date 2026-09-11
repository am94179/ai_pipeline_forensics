"""Load evaluation-only scenario expectations without exposing them to agents."""

from __future__ import annotations

import json
from pathlib import Path

from .models import EvaluationCase


SCENARIO_IDS = ("enum_change", "null_rate_increase", "missing_partition")


def load_evaluation_cases(scenarios_root: Path) -> list[EvaluationCase]:
    """Load the fixed local suite from scenario ground-truth artifacts."""
    cases: list[EvaluationCase] = []
    for scenario_id in SCENARIO_IDS:
        path = scenarios_root / scenario_id / "ground_truth" / "ground_truth.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        evaluation = payload.get("evaluation")
        if not isinstance(evaluation, dict):
            raise ValueError(f"Scenario '{scenario_id}' has no evaluation contract.")
        cases.append(EvaluationCase(scenario_id=scenario_id, **evaluation))
    if len({case.scenario_id for case in cases}) != len(cases):
        raise ValueError("Evaluation scenario IDs must be unique.")
    return cases
