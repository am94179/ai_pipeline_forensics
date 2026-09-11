"""Inspect CSV dataset schemas with deterministic type inference."""

from __future__ import annotations

from pathlib import Path

from .common import ToolInputError, dataset_path, read_csv_rows


def inspect_schema(scenario_dir: Path, dataset: str) -> dict[str, object]:
    """Return column names, inferred types, and nullability for a public dataset."""
    rows = read_csv_rows(dataset_path(scenario_dir, dataset))
    if not rows:
        raise ToolInputError(f"Dataset '{dataset}' contains no rows; schema cannot be inferred.")

    columns = []
    for column in rows[0]:
        values = [row[column] for row in rows]
        columns.append(
            {
                "name": column,
                "type": _infer_type(values),
                "nullable": any(value == "" for value in values),
            }
        )
    return {"dataset": dataset, "columns": columns}


def _infer_type(values: list[str]) -> str:
    non_null_values = [value for value in values if value != ""]
    if not non_null_values:
        return "VARCHAR"
    if all(_is_int(value) for value in non_null_values):
        return "BIGINT"
    if all(_is_float(value) for value in non_null_values):
        return "DOUBLE"
    return "VARCHAR"


def _is_int(value: str) -> bool:
    try:
        int(value)
    except ValueError:
        return False
    return True


def _is_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True

