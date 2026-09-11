"""Basic construction test for the active LangGraph workflow."""

from __future__ import annotations

from pathlib import Path


from investigator.agent.graph import build_investigation_graph


def _initial_state() -> dict:
    scenario_dir = Path(__file__).resolve().parents[2] / "data/scenarios/enum_change"
    return {
        "incident": {
            "incident_id": "enum-change-2026-09-02",
            "description": "Revenue-reporting output dropped.",
            "scenario_dir": str(scenario_dir),
        }
    }


def test_build_investigation_graph_requires_no_llm_configuration() -> None:
    graph = build_investigation_graph()

    assert graph is not None


