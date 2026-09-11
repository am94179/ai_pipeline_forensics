"""Generate a deterministic null-rate increase incident scenario."""

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


SCENARIO_ID = "null_rate_increase"
SEED = 20260909
BASELINE_DATE = "2026-09-01"
INCIDENT_DATE = "2026-09-02"
TOTAL_ORDERS = 1_000
NULL_AMOUNT_COUNT = 300


def generate_scenario(output_dir: Path) -> ScenarioManifest:
    """Write public evidence and evaluation-only ground truth for this incident."""
    baseline_source = build_orders(BASELINE_DATE, TOTAL_ORDERS, SEED)
    incident_source = build_orders(INCIDENT_DATE, TOTAL_ORDERS, SEED)
    for index in [*range(200), *range(600, 700)]:
        incident_source[index]["amount"] = None

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
            "source": "orders_api",
            "transformation": "select completed orders with non-null amounts for revenue reporting",
            "destination": "warehouse.daily_revenue_orders",
            "filter": {"field": "order_status", "equals": "completed"},
            "required_fields": ["amount"],
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
                component="transformation",
                message="Validated revenue orders with non-null amounts.",
                context={"records_written": len(baseline_output), "null_amounts": 0},
            ),
            LogEvent(
                timestamp=f"{INCIDENT_DATE}T01:02:00Z",
                level="WARN",
                pipeline=PIPELINE_NAME,
                component="transformation",
                message="Dropped completed orders with null amounts during revenue validation.",
                context={"records_written": len(incident_output), "null_amounts": NULL_AMOUNT_COUNT},
            ),
            LogEvent(
                timestamp=f"{INCIDENT_DATE}T01:03:00Z",
                level="INFO",
                pipeline=PIPELINE_NAME,
                component="warehouse_load",
                message="Pipeline completed successfully.",
                context={"status": "SUCCESS", "records_written": len(incident_output)},
            ),
        ],
    )

    manifest = ScenarioManifest(
        scenario_id=SCENARIO_ID,
        description=(
            "Upstream orders suddenly contain null amount values, and revenue validation "
            "drops completed orders whose amount is missing."
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
            root_cause="The upstream producer emitted null order amounts, violating a revenue-required field.",
            impact="200 completed orders were dropped and revenue output fell from 600 to 400 rows.",
            expected_evidence=[
                "Incident source row count remains 1000 while amount null rate increases to 30 percent.",
                "Incident revenue output falls from 600 to 400 rows.",
                "Transformation logs record completed orders dropped for null amounts.",
                "Pipeline configuration lists amount as a required field.",
            ],
            evaluation={
                "root_cause_label": "null_rate_increase",
                "accepted_keywords": ["null amount", "null"],
                "required_evidence_ids": ["E03", "E04", "E05"],
                "allowed_ambiguity": [],
            },
        ).as_dict(),
    )
    return manifest
