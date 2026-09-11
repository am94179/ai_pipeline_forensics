"""Phase 1 contract tests for the enum-change scenario."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from investigator.synthetic.enum_change import generate_scenario


def test_generation_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_scenario(first)
    generate_scenario(second)

    first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    assert first_files == second_files
    for relative_path in first_files:
        assert (first / relative_path).read_bytes() == (second / relative_path).read_bytes(), relative_path.as_posix()

def test_incident_evidence_is_consistent(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "enum_change"
    generate_scenario(scenario_dir)

    baseline_source = _read_csv(scenario_dir / "source" / "baseline_orders.csv")
    incident_source = _read_csv(scenario_dir / "source" / "incident_orders.csv")
    baseline_output = _read_csv(scenario_dir / "warehouse" / "baseline_revenue_orders.csv")
    incident_output = _read_csv(scenario_dir / "warehouse" / "incident_revenue_orders.csv")
    pipeline_runs = json.loads((scenario_dir / "metadata" / "pipeline_runs.json").read_text())
    pipeline_config = json.loads((scenario_dir / "metadata" / "pipeline_config.json").read_text())

    assert len(baseline_source) == 1_000
    assert len(incident_source) == 1_000
    assert sum(row["order_status"] == "COMPLETE" for row in incident_source) == 450
    assert len(baseline_output) == 600
    assert len(incident_output) == 150
    assert pipeline_config["filter"]["equals"] == "completed"
    assert [run["status"] for run in pipeline_runs] == ["SUCCESS", "SUCCESS"]
    assert [run["records_written"] for run in pipeline_runs] == [600, 150]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))



