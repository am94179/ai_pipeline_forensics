"""Deterministic profiling and comparison of local scenario datasets."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean, median

from .common import ToolInputError, dataset_path, read_csv_rows, require_columns
from .schema import _is_float


def profile_dataset(
    scenario_dir: Path,
    dataset: str,
    categorical_columns: list[str] | None = None,
    sample_size: int = 5,
) -> dict[str, object]:
    """Calculate row, null, uniqueness, numeric, and categorical metrics."""
    if sample_size < 1:
        raise ToolInputError("sample_size must be at least 1.")
    rows = read_csv_rows(dataset_path(scenario_dir, dataset))
    if not rows:
        raise ToolInputError(f"Dataset '{dataset}' contains no rows to profile.")

    column_names = list(rows[0])
    if categorical_columns is not None:
        require_columns(rows, categorical_columns)
    selected_categoricals = categorical_columns or [
        column for column in column_names if not all(_is_float(row[column]) for row in rows if row[column] != "")
    ]

    columns: dict[str, dict[str, object]] = {}
    for column in column_names:
        values = [row[column] for row in rows]
        non_null_values = [value for value in values if value != ""]
        unique_values = set(non_null_values)
        column_profile: dict[str, object] = {
            "null_count": len(values) - len(non_null_values),
            "null_rate": _rate(len(values) - len(non_null_values), len(values)),
            "unique_count": len(unique_values),
            "unique_rate": _rate(len(unique_values), len(non_null_values)),
            "sample_values": non_null_values[:sample_size],
        }
        if non_null_values and all(_is_float(value) for value in non_null_values):
            numeric_values = [float(value) for value in non_null_values]
            column_profile["numeric_summary"] = {
                "min": min(numeric_values),
                "max": max(numeric_values),
                "mean": round(mean(numeric_values), 4),
                "median": round(median(numeric_values), 4),
            }
        if column in selected_categoricals:
            counts = Counter(non_null_values)
            column_profile["distribution"] = {
                value: {"count": count, "rate": _rate(count, len(non_null_values))}
                for value, count in sorted(counts.items())
            }
        columns[column] = column_profile

    return {"dataset": dataset, "row_count": len(rows), "columns": columns}


def compare_distributions(
    scenario_dir: Path,
    baseline_dataset: str,
    incident_dataset: str,
    categorical_columns: list[str],
) -> dict[str, object]:
    """Compare row counts and categorical distributions across two datasets."""
    baseline = profile_dataset(scenario_dir, baseline_dataset, categorical_columns)
    incident = profile_dataset(scenario_dir, incident_dataset, categorical_columns)
    baseline_rows = int(baseline["row_count"])
    incident_rows = int(incident["row_count"])

    changes: dict[str, dict[str, dict[str, object]]] = {}
    for column in categorical_columns:
        baseline_distribution = baseline["columns"][column].get("distribution", {})
        incident_distribution = incident["columns"][column].get("distribution", {})
        values = sorted(set(baseline_distribution) | set(incident_distribution))
        changes[column] = {
            value: {
                "baseline_count": baseline_distribution.get(value, {}).get("count", 0),
                "incident_count": incident_distribution.get(value, {}).get("count", 0),
                "count_delta": incident_distribution.get(value, {}).get("count", 0)
                - baseline_distribution.get(value, {}).get("count", 0),
                "rate_delta": round(
                    incident_distribution.get(value, {}).get("rate", 0.0)
                    - baseline_distribution.get(value, {}).get("rate", 0.0),
                    6,
                ),
            }
            for value in values
        }

    return {
        "baseline_dataset": baseline_dataset,
        "incident_dataset": incident_dataset,
        "row_count": {
            "baseline": baseline_rows,
            "incident": incident_rows,
            "delta": incident_rows - baseline_rows,
            "change_rate": _rate(incident_rows - baseline_rows, baseline_rows),
        },
        "categorical_distribution_changes": changes,
    }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0

