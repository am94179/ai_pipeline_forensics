"""Tests for the local enum-change demonstration entry point."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from investigator.agent.state import FinalReport


def test_demo_script_prints_final_report_with_fake_graph(monkeypatch, capsys) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts/investigate_enum_change.py"
    specification = importlib.util.spec_from_file_location(
        "investigate_enum_change", script_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    received_states: list[dict] = []

    class FakeGraph:
        def invoke(self, state: dict) -> dict:
            received_states.append(state)
            return {
                "analysis": object(),
                "final_report": FinalReport(
                    incident_id="enum-change-2026-09-02",
                    summary="Fake report.",
                ),
            }

    monkeypatch.setattr(module, "build_investigation_graph", lambda: FakeGraph())

    assert module.main() == 0

    assert received_states[0]["incident"]["incident_id"] == "enum-change-2026-09-02"
    assert "Fake report." in capsys.readouterr().out
