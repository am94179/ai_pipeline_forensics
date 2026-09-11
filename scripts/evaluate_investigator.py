#!/usr/bin/env python3
"""Run one local evaluation candidate and write a deterministic JSON report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from investigator.evaluation.baselines import STATIC_RULES_CANDIDATE  # noqa: E402
from investigator.evaluation.runner import (  # noqa: E402
    INVESTIGATOR_WORKFLOW_CANDIDATE,
    run_evaluation,
    write_evaluation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        choices=[STATIC_RULES_CANDIDATE, INVESTIGATOR_WORKFLOW_CANDIDATE],
        default=STATIC_RULES_CANDIDATE,
        help="Candidate to evaluate. investigator_workflow may invoke the configured LLM.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Explicit JSON output path.")
    args = parser.parse_args()

    report = run_evaluation(
        candidate_name=args.candidate,
        scenarios_root=PROJECT_ROOT / "data" / "scenarios",
    )
    write_evaluation_report(report, args.output)
    print(f"Wrote {args.candidate} evaluation for {report.aggregate['scenario_count']} scenarios to {args.output}")
    print(json_summary(report))
    return 0


def json_summary(report: object) -> str:
    aggregate = report.aggregate
    return (
        f"root_cause_match_rate={aggregate['root_cause_match_rate']}, "
        f"required_evidence_rate={aggregate['required_evidence_rate']}, "
        f"citation_validity_rate={aggregate['citation_validity_rate']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
