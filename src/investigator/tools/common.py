"""Shared file and dataset helpers for deterministic tools."""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATASET_PATHS = {
    "baseline_source_orders": "source/baseline_orders.csv",
    "incident_source_orders": "source/incident_orders.csv",
    "baseline_transformed_orders": "transformed/baseline_revenue_orders.csv",
    "incident_transformed_orders": "transformed/incident_revenue_orders.csv",
    "baseline_warehouse_orders": "warehouse/baseline_revenue_orders.csv",
    "incident_warehouse_orders": "warehouse/incident_revenue_orders.csv",
}


class ToolInputError(ValueError):
    """Raised when a tool request cannot be fulfilled safely or unambiguously."""


def dataset_path(scenario_dir: Path, dataset: str) -> Path:
    """Resolve a named public dataset and reject unregistered or missing artifacts."""
    try:
        relative_path = DATASET_PATHS[dataset]
    except KeyError as error:
        allowed = ", ".join(sorted(DATASET_PATHS))
        raise ToolInputError(f"Unknown dataset '{dataset}'. Available datasets: {allowed}.") from error

    path = scenario_dir / relative_path
    if not path.is_file():
        raise ToolInputError(f"Dataset artifact does not exist: {path}")
    return path


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> object:
    if not path.is_file():
        raise ToolInputError(f"Artifact does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def require_columns(rows: list[dict[str, str]], columns: list[str]) -> None:
    available = set(rows[0]) if rows else set()
    unknown = sorted(set(columns) - available)
    if unknown:
        raise ToolInputError(f"Unknown column(s): {', '.join(unknown)}.")

