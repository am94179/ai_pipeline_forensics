"""Small shared helpers for deterministic synthetic scenario generators."""

from __future__ import annotations

import csv
import json
import random
from collections.abc import Iterable, Mapping
from pathlib import Path

from investigator.models import LogEvent, PipelineRun


ORDER_FIELDS = ("order_id", "customer_id", "order_status", "amount", "created_at")
PIPELINE_NAME = "orders_daily_revenue"


def build_orders(run_date: str, count: int, seed: int) -> list[dict[str, object]]:
    """Build deterministic orders with a stable 60-percent completed rate."""
    rng = random.Random(seed)
    completed_count = int(count * 0.6)
    orders: list[dict[str, object]] = []
    for index in range(1, count + 1):
        if index <= completed_count:
            status = "completed"
        elif index <= int(count * 0.85):
            status = "pending"
        else:
            status = "cancelled"
        orders.append(
            {
                "order_id": f"ORD-{run_date.replace('-', '')}-{index:04d}",
                "customer_id": f"CUST-{rng.randint(1, 350):04d}",
                "order_status": status,
                "amount": round(rng.uniform(15.0, 450.0), 2),
                "created_at": f"{run_date}T{index % 24:02d}:{index % 60:02d}:00Z",
            }
        )
    return orders


def revenue_orders(orders: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Retain completed orders with a non-null amount for revenue reporting."""
    return [
        dict(order)
        for order in orders
        if order["order_status"] == "completed" and order["amount"] not in (None, "")
    ]


def write_csv(path: Path, records: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORDER_FIELDS)
        writer.writeheader()
        writer.writerows(records)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path: Path, events: Iterable[LogEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.as_dict(), sort_keys=True))
            handle.write("\n")


def pipeline_run(run_date: str, records_read: int, records_written: int) -> dict[str, object]:
    return PipelineRun(
        pipeline_name=PIPELINE_NAME,
        run_id=f"{PIPELINE_NAME}-{run_date}",
        run_date=run_date,
        status="SUCCESS",
        started_at=f"{run_date}T01:00:00Z",
        completed_at=f"{run_date}T01:03:00Z",
        records_read=records_read,
        records_written=records_written,
    ).as_dict()


def standard_artifact_paths() -> dict[str, list[str]]:
    return {
        "source": ["source/baseline_orders.csv", "source/incident_orders.csv"],
        "transformed": [
            "transformed/baseline_revenue_orders.csv",
            "transformed/incident_revenue_orders.csv",
        ],
        "warehouse": [
            "warehouse/baseline_revenue_orders.csv",
            "warehouse/incident_revenue_orders.csv",
        ],
        "metadata": ["metadata/pipeline_config.json", "metadata/pipeline_runs.json"],
        "logs": ["logs/pipeline_events.jsonl"],
    }
