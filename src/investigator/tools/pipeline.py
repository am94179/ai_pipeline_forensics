"""Read simulated pipeline metadata without exposing scenario ground truth."""

from __future__ import annotations

from pathlib import Path

from .common import ToolInputError, read_json


def get_pipeline_status(scenario_dir: Path, run_date: str | None = None) -> dict[str, object]:
    """Return pipeline run metadata, optionally limited to one run date."""
    runs = read_json(scenario_dir / "metadata" / "pipeline_runs.json")
    if not isinstance(runs, list):
        raise ToolInputError("pipeline_runs.json must contain a list of pipeline runs.")
    matching_runs = [run for run in runs if not run_date or run.get("run_date") == run_date]
    if run_date and not matching_runs:
        raise ToolInputError(f"No pipeline run exists for date '{run_date}'.")
    return {"run_count": len(matching_runs), "runs": matching_runs}


def inspect_pipeline_metadata(scenario_dir: Path) -> dict[str, object]:
    """Return the public pipeline configuration artifact for a scenario."""
    metadata = read_json(scenario_dir / "metadata" / "pipeline_config.json")
    if not isinstance(metadata, dict):
        raise ToolInputError("pipeline_config.json must contain an object.")
    return metadata

