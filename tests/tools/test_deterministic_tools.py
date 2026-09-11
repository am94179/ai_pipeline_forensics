"""Phase 2 contract tests for deterministic investigation tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from investigator.synthetic.enum_change import generate_scenario
from investigator.tools import (
    compare_distributions,
    get_pipeline_status,
    inspect_pipeline_metadata,
    inspect_schema,
    profile_dataset,
    query_data,
    search_logs,
)
from investigator.tools.common import ToolInputError


@pytest.fixture
def scenario_dir(tmp_path: Path) -> Path:
    scenario = tmp_path / "enum_change"
    generate_scenario(scenario)
    return scenario


def test_search_logs_returns_targeted_pipeline_events(scenario_dir: Path) -> None:
    result = search_logs(
        scenario_dir,
        query="completed-order",
        start_time="2026-09-02T00:00:00Z",
        component="transformation",
    )

    assert result["match_count"] == 1
    assert result["events"][0]["context"]["records_written"] == 150


def test_query_data_reads_named_datasets_and_rejects_mutation(scenario_dir: Path) -> None:
    result = query_data(
        scenario_dir,
        "SELECT count(*) AS complete_count FROM incident_source_orders WHERE order_status = 'COMPLETE'",
    )

    assert result["columns"] == ["complete_count"]
    assert result["rows"] == [{"complete_count": 450}]
    with pytest.raises(ToolInputError, match="Only one SELECT or WITH query"):
        query_data(scenario_dir, "DELETE FROM incident_source_orders")
    with pytest.raises(ToolInputError, match="Only one SELECT or WITH query"):
        query_data(scenario_dir, "WITH source AS (SELECT 1) DELETE FROM incident_source_orders")


def test_inspect_schema_returns_inferred_columns(scenario_dir: Path) -> None:
    result = inspect_schema(scenario_dir, "incident_source_orders")

    assert result["dataset"] == "incident_source_orders"
    assert result["columns"] == [
        {"name": "order_id", "type": "VARCHAR", "nullable": False},
        {"name": "customer_id", "type": "VARCHAR", "nullable": False},
        {"name": "order_status", "type": "VARCHAR", "nullable": False},
        {"name": "amount", "type": "DOUBLE", "nullable": False},
        {"name": "created_at", "type": "VARCHAR", "nullable": False},
    ]


def test_profile_dataset_returns_deterministic_metrics(scenario_dir: Path) -> None:
    result = profile_dataset(scenario_dir, "incident_source_orders", categorical_columns=["order_status"])

    assert result["row_count"] == 1_000
    assert result["columns"]["order_status"]["distribution"]["COMPLETE"] == {
        "count": 450,
        "rate": 0.45,
    }
    assert result["columns"]["amount"]["null_rate"] == 0.0


def test_pipeline_metadata_and_status_are_available(scenario_dir: Path) -> None:
    metadata = inspect_pipeline_metadata(scenario_dir)
    status = get_pipeline_status(scenario_dir, run_date="2026-09-02")

    assert metadata["filter"] == {"field": "order_status", "equals": "completed"}
    assert status == {
        "run_count": 1,
        "runs": [
            {
                "completed_at": "2026-09-02T01:03:00Z",
                "pipeline_name": "orders_daily_revenue",
                "records_read": 1_000,
                "records_written": 150,
                "run_date": "2026-09-02",
                "run_id": "orders_daily_revenue-2026-09-02",
                "started_at": "2026-09-02T01:00:00Z",
                "status": "SUCCESS",
            }
        ],
    }


def test_compare_distributions_surfaces_enum_change(scenario_dir: Path) -> None:
    result = compare_distributions(
        scenario_dir,
        "baseline_source_orders",
        "incident_source_orders",
        categorical_columns=["order_status"],
    )

    assert result["row_count"] == {"baseline": 1_000, "incident": 1_000, "delta": 0, "change_rate": 0.0}
    status_changes = result["categorical_distribution_changes"]["order_status"]
    assert status_changes["COMPLETE"]["baseline_count"] == 0
    assert status_changes["COMPLETE"]["incident_count"] == 450
    assert status_changes["completed"]["count_delta"] == -450


def test_tools_reject_unknown_or_invalid_inputs(scenario_dir: Path) -> None:
    with pytest.raises(ToolInputError, match="Unknown dataset"):
        inspect_schema(scenario_dir, "ground_truth")
    with pytest.raises(ToolInputError, match="start_time must not"):
        search_logs(scenario_dir, start_time="2026-09-03T00:00:00Z", end_time="2026-09-02T00:00:00Z")

