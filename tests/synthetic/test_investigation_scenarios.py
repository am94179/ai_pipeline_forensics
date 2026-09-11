"""Investigation scenario generation and deterministic-tool integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from investigator.synthetic.missing_partition import generate_scenario as generate_missing_partition
from investigator.synthetic.null_rate_increase import generate_scenario as generate_null_rate_increase
from investigator.tools import (
    compare_distributions,
    get_pipeline_status,
    inspect_pipeline_metadata,
    profile_dataset,
    search_logs,
)


@pytest.mark.parametrize(
    ("generator", "scenario_id"),
    [
        (generate_null_rate_increase, "null_rate_increase"),
        (generate_missing_partition, "missing_partition"),
    ],
)
def test_investigation_scenarios_generate_deterministically(
    tmp_path: Path,
    generator: object,
    scenario_id: str,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generator(first)  # type: ignore[operator]
    generator(second)  # type: ignore[operator]

    first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    assert first_files == second_files
    assert (first / "manifest.json").is_file()
    assert (first / "ground_truth" / "ground_truth.json").is_file()
    assert json.loads((first / "manifest.json").read_text(encoding="utf-8"))["scenario_id"] == scenario_id
    for relative_path in first_files:
        assert (first / relative_path).read_bytes() == (second / relative_path).read_bytes()


def test_null_rate_scenario_is_inspectable_with_phase_2_tools(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "null_rate_increase"
    generate_null_rate_increase(scenario_dir)

    profile = profile_dataset(scenario_dir, "incident_source_orders")
    comparison = compare_distributions(
        scenario_dir,
        "baseline_warehouse_orders",
        "incident_warehouse_orders",
        ["order_status"],
    )
    logs = search_logs(scenario_dir, query="null amounts", level="WARN")
    metadata = inspect_pipeline_metadata(scenario_dir)

    assert profile["row_count"] == 1_000
    assert profile["columns"]["amount"]["null_count"] == 300
    assert profile["columns"]["amount"]["null_rate"] == 0.3
    assert comparison["row_count"] == {"baseline": 600, "incident": 400, "delta": -200, "change_rate": -0.333333}
    assert logs["match_count"] == 1
    assert metadata["required_fields"] == ["amount"]


def test_missing_partition_scenario_is_inspectable_with_phase_2_tools(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "missing_partition"
    generate_missing_partition(scenario_dir)

    status = get_pipeline_status(scenario_dir)
    comparison = compare_distributions(
        scenario_dir,
        "baseline_source_orders",
        "incident_source_orders",
        ["order_status"],
    )
    logs = search_logs(scenario_dir, query="partition", level="WARN")
    metadata = inspect_pipeline_metadata(scenario_dir)

    assert [run["records_read"] for run in status["runs"]] == [1_000, 750]
    assert comparison["row_count"] == {"baseline": 1_000, "incident": 750, "delta": -250, "change_rate": -0.25}
    assert logs["match_count"] == 1
    assert metadata["partitioning"]["expected_partitions"] == 24
