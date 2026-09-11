"""Search structured JSONL pipeline logs deterministically."""

from __future__ import annotations

import json
from pathlib import Path

from .common import ToolInputError


def search_logs(
    scenario_dir: Path,
    query: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    level: str | None = None,
    component: str | None = None,
) -> dict[str, object]:
    """Return public log events matching optional text and structured filters."""
    if start_time and end_time and start_time > end_time:
        raise ToolInputError("start_time must not be later than end_time.")

    log_path = scenario_dir / "logs" / "pipeline_events.jsonl"
    if not log_path.is_file():
        raise ToolInputError(f"Log artifact does not exist: {log_path}")

    matches: list[dict[str, object]] = []
    normalized_query = query.lower() if query else None
    for line in log_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if start_time and event["timestamp"] < start_time:
            continue
        if end_time and event["timestamp"] > end_time:
            continue
        if level and event["level"] != level:
            continue
        if component and event["component"] != component:
            continue
        if normalized_query and normalized_query not in json.dumps(event, sort_keys=True).lower():
            continue
        matches.append(event)

    return {
        "match_count": len(matches),
        "filters": {
            "query": query,
            "start_time": start_time,
            "end_time": end_time,
            "level": level,
            "component": component,
        },
        "events": matches,
    }

