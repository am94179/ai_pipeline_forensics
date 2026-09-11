"""Run the bounded investigator against the enum-change scenario."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from investigator.agent.graph import build_investigation_graph  # noqa: E402


def main() -> int:
    """Run the graph and print the final structured report."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    initial_state = {
        "incident": {
            "incident_id": "enum-change-2026-09-02",
            "description": "Revenue-reporting output dropped.",
            "scenario_dir": str(PROJECT_ROOT / "data/scenarios/enum_change"),
        }
    }
    result = build_investigation_graph().invoke(initial_state)
    report = result.get("final_report")
    if report is None:
        logging.getLogger(__name__).error("Investigation did not produce a final report.")
        return 1

    print(report.model_dump_json(indent=2))
    if result.get("analysis") is None:
        logging.getLogger(__name__).error(
            "Analysis was unavailable; configure the LLM settings in .env to run the full investigation."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
