"""Generate a deterministic missing-partition incident scenario."""

from __future__ import annotations

from pathlib import Path

from investigator.models import GroundTruth, LogEvent, ScenarioManifest
from investigator.synthetic.scenario_utils import (
    PIPELINE_NAME,
    build_orders,
    pipeline_run,
    revenue_orders,
    standard_artifact_paths,
    write_csv,
    write_json,
    write_jsonl,
)


SCENARIO_ID = "missing_partition"
SEED = 20260910
BASELINE_DATE = "2026-09-01"
INCIDENT_DATE = "2026-09-02"
BASELINE_ORDERS = 1_000
INCIDENT_ORDERS = 750


def generate_scenario(output_dir: Path) -> ScenarioManifest:
    """Write public evidence and evaluation-only ground truth for this incident."""
    baseline_source = build_orders(BASELINE_DATE, BASELINE_ORDERS, SEED)
    incident_source = build_orders(INCIDENT_DATE, INCIDENT_ORDERS, SEED)
    baseline_output = revenue_orders(baseline_source)
    incident_output = revenue_orders(incident_source)
    write_csv(output_dir / "source" / "baseline_orders.csv", baseline_source)
    write_csv(output_dir / "source" / "incident_orders.csv", incident_source)
    write_csv(output_dir / "transformed" / "baseline_revenue_orders.csv", baseline_output)
    write_csv(output_dir / "transformed" / "incident_revenue_orders.csv", incident_output)
    write_csv(output_dir / "warehouse" / "baseline_revenue_orders.csv", baseline_output)
    write_csv(output_dir / "warehouse" / "incident_revenue_orders.csv", incident_output)

    write_json(
        output_dir / "metadata" / "pipeline_config.json",
        {
            "pipeline_name": PIPELINE_NAME,
            "source": "orders_api_hourly_partitions",
            "transformation": "select completed orders for revenue reporting",
            "destination": "warehouse.daily_revenue_orders",
            "partitioning": {"field": "created_at", "expected_partitions": 24},
            "filter": {"field": "order_status", "equals": "completed"},
        },
    )
    write_json(
        output_dir / "metadata" / "pipeline_runs.json",
        [
            pipeline_run(BASELINE_DATE, len(baseline_source), len(baseline_output)),
            pipeline_run(INCIDENT_DATE, len(incident_source), len(incident_output)),
        ],
    )
    write_jsonl(
        output_dir / "logs" / "pipeline_events.jsonl",
        [
            LogEvent(
                timestamp=f"{BASELINE_DATE}T01:02:00Z",
                level="INFO",
                pipeline=PIPELINE_NAME,
                component="ingestion",
                message="Read all expected hourly source partitions.",
                context={"records_read": len(baseline_source), "partitions_read": 24},
            ),
            LogEvent(
                timestamp=f"{INCIDENT_DATE}T01:00:00Z",
                level="WARN",
                pipeline=PIPELINE_NAME,
                component="ingestion",
                message="One expected hourly source partition was unavailable.",
                context={"records_read": len(incident_source), "partitions_read": 18, "partitions_expected": 24},
            ),
            LogEvent(
                timestamp=f"{INCIDENT_DATE}T01:03:00Z",
                level="INFO",
                pipeline=PIPELINE_NAME,
                component="warehouse_load",
                message="Pipeline completed successfully with available partitions.",
                context={"status": "SUCCESS", "records_written": len(incident_output)},
            ),
        ],
    )

    manifest = ScenarioManifest(
        scenario_id=SCENARIO_ID,
        description=(
            "A daily orders pipeline completes after an expected source partition is unavailable, "
            "leaving downstream revenue output incomplete."
        ),
        random_seed=SEED,
        baseline_date=BASELINE_DATE,
        incident_date=INCIDENT_DATE,
        artifact_paths=standard_artifact_paths(),
    )
    write_json(output_dir / "manifest.json", manifest.as_dict())
    write_json(
        output_dir / "ground_truth" / "ground_truth.json",
        GroundTruth(
            root_cause="An expected source partition was unavailable during ingestion.",
            impact="Source volume fell from 1000 to 750 rows and revenue output fell from 600 to 450 rows.",
            expected_evidence=[
                "Incident source and pipeline records_read values fall from 1000 to 750.",
                "Warehouse revenue output falls from 600 to 450 rows.",
                "Ingestion logs record unavailable expected source partition(s).",
                "Pipeline configuration expects hourly partitions.",
            ],
            evaluation={
                "root_cause_label": "missing_partition",
                "accepted_keywords": ["partition", "incomplete ingestion"],
                "required_evidence_ids": ["E01", "E02", "E05"],
                "allowed_ambiguity": ["reduced source volume"],
            },
        ).as_dict(),
    )
    return manifest
