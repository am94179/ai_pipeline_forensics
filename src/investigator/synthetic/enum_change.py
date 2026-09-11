"""Generate a deterministic enum-change pipeline incident scenario."""

from __future__ import annotations

import csv
import json
import random
from collections.abc import Iterable
from pathlib import Path

from investigator.models import GroundTruth, LogEvent, OrderRecord, PipelineRun, ScenarioManifest

SCENARIO_ID = "enum_change"
SEED = 20260908
BASELINE_DATE = "2026-09-01"
INCIDENT_DATE = "2026-09-02"
PIPELINE_NAME = "orders_daily_revenue"
TOTAL_ORDERS = 1_000
COMPLETED_ORDERS = 600
RENAMED_COMPLETED_ORDERS = 450
ORDER_FIELDS = ("order_id", "customer_id", "order_status", "amount", "created_at")


def _build_orders(run_date: str, incident: bool) -> list[OrderRecord]:
    """Create a fixed-size source dataset with a controlled status distribution."""
    rng = random.Random(SEED)
    orders: list[OrderRecord] = []
    for index in range(1, TOTAL_ORDERS + 1):
        if index <= COMPLETED_ORDERS:
            status = "completed"
            if incident and index <= RENAMED_COMPLETED_ORDERS:
                status = "COMPLETE"
        elif index <= 850:
            status = "pending"
        else:
            status = "cancelled"
        orders.append(
            OrderRecord(
                order_id=f"ORD-{run_date.replace('-', '')}-{index:04d}",
                customer_id=f"CUST-{rng.randint(1, 350):04d}",
                order_status=status,
                amount=round(rng.uniform(15.0, 450.0), 2),
                created_at=f"{run_date}T{index % 24:02d}:{index % 60:02d}:00Z",
            )
        )
    return orders


def _write_csv(path: Path, records: Iterable[OrderRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORDER_FIELDS)
        writer.writeheader()
        writer.writerows(record.as_dict() for record in records)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_jsonl(path: Path, events: Iterable[LogEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.as_dict(), sort_keys=True))
            handle.write("\n")


def _run_metadata(run_date: str, records_written: int) -> PipelineRun:
    return PipelineRun(
        pipeline_name=PIPELINE_NAME,
        run_id=f"{PIPELINE_NAME}-{run_date}",
        run_date=run_date,
        status="SUCCESS",
        started_at=f"{run_date}T01:00:00Z",
        completed_at=f"{run_date}T01:03:00Z",
        records_read=TOTAL_ORDERS,
        records_written=records_written,
    )


def generate_scenario(output_dir: Path) -> ScenarioManifest:
    """Write all public evidence and private ground truth for this scenario."""
    baseline_source = _build_orders(BASELINE_DATE, incident=False)
    incident_source = _build_orders(INCIDENT_DATE, incident=True)
    baseline_output = [row for row in baseline_source if row.order_status == "completed"]
    incident_output = [row for row in incident_source if row.order_status == "completed"]

    _write_csv(output_dir / "source" / "baseline_orders.csv", baseline_source)
    _write_csv(output_dir / "source" / "incident_orders.csv", incident_source)
    _write_csv(output_dir / "transformed" / "baseline_revenue_orders.csv", baseline_output)
    _write_csv(output_dir / "transformed" / "incident_revenue_orders.csv", incident_output)
    _write_csv(output_dir / "warehouse" / "baseline_revenue_orders.csv", baseline_output)
    _write_csv(output_dir / "warehouse" / "incident_revenue_orders.csv", incident_output)

    _write_json(
        output_dir / "metadata" / "pipeline_config.json",
        {
            "pipeline_name": PIPELINE_NAME,
            "source": "orders_api",
            "transformation": "select completed orders for revenue reporting",
            "destination": "warehouse.daily_revenue_orders",
            "filter": {"field": "order_status", "equals": "completed"},
        },
    )
    _write_json(
        output_dir / "metadata" / "pipeline_runs.json",
        [
            _run_metadata(BASELINE_DATE, len(baseline_output)).as_dict(),
            _run_metadata(INCIDENT_DATE, len(incident_output)).as_dict(),
        ],
    )

    events = [
        LogEvent(
            timestamp=f"{BASELINE_DATE}T01:00:00Z",
            level="INFO",
            pipeline=PIPELINE_NAME,
            component="ingestion",
            message="Read source orders successfully.",
            context={"records_read": TOTAL_ORDERS},
        ),
        LogEvent(
            timestamp=f"{BASELINE_DATE}T01:02:00Z",
            level="INFO",
            pipeline=PIPELINE_NAME,
            component="transformation",
            message="Applied completed-order revenue filter.",
            context={"filter": "order_status = 'completed'", "records_written": len(baseline_output)},
        ),
        LogEvent(
            timestamp=f"{INCIDENT_DATE}T01:00:00Z",
            level="INFO",
            pipeline=PIPELINE_NAME,
            component="ingestion",
            message="Read source orders successfully.",
            context={"records_read": TOTAL_ORDERS},
        ),
        LogEvent(
            timestamp=f"{INCIDENT_DATE}T01:02:00Z",
            level="INFO",
            pipeline=PIPELINE_NAME,
            component="transformation",
            message="Applied completed-order revenue filter.",
            context={"filter": "order_status = 'completed'", "records_written": len(incident_output)},
        ),
        LogEvent(
            timestamp=f"{INCIDENT_DATE}T01:03:00Z",
            level="INFO",
            pipeline=PIPELINE_NAME,
            component="warehouse_load",
            message="Pipeline completed successfully.",
            context={"status": "SUCCESS", "records_written": len(incident_output)},
        ),
    ]
    _write_jsonl(output_dir / "logs" / "pipeline_events.jsonl", events)

    manifest = ScenarioManifest(
        scenario_id=SCENARIO_ID,
        description=(
            "An upstream producer renames completed order_status values to COMPLETE, "
            "while downstream revenue logic still filters for completed."
        ),
        random_seed=SEED,
        baseline_date=BASELINE_DATE,
        incident_date=INCIDENT_DATE,
        artifact_paths={
            "source": ["source/baseline_orders.csv", "source/incident_orders.csv"],
            "transformed": ["transformed/baseline_revenue_orders.csv", "transformed/incident_revenue_orders.csv"],
            "warehouse": ["warehouse/baseline_revenue_orders.csv", "warehouse/incident_revenue_orders.csv"],
            "metadata": ["metadata/pipeline_config.json", "metadata/pipeline_runs.json"],
            "logs": ["logs/pipeline_events.jsonl"],
        },
    )
    _write_json(output_dir / "manifest.json", manifest.as_dict())
    _write_json(
        output_dir / "ground_truth" / "ground_truth.json",
        GroundTruth(
            root_cause=(
                "The upstream producer changed order_status from completed to COMPLETE, "
                "but the revenue transformation still filters only for completed."
            ),
            impact=(
                "450 of 600 completed-order revenue records were excluded on the incident day; "
                "the reporting output fell by 75 percent."
            ),
            expected_evidence=[
                "Source row count remains 1000 on both days.",
                "Incident source data contains 450 COMPLETE values.",
                "Revenue output falls from 600 to 150 rows.",
                "Pipeline configuration filters for order_status = completed.",
                "Incident pipeline run reports SUCCESS rather than an ingestion failure.",
            ],
            evaluation={
                "root_cause_label": "enum_value_mismatch",
                "accepted_keywords": ["enum", "order_status", "complete"],
                "required_evidence_ids": ["E02", "E03", "E05"],
                "allowed_ambiguity": [],
            },
        ).as_dict(),
    )
    return manifest

