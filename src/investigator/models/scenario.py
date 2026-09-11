"""Small, serializable models for synthetic incident scenarios."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class OrderRecord:
    """A single order at one stage of the simulated pipeline."""

    order_id: str
    customer_id: str
    order_status: str
    amount: float
    created_at: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PipelineRun:
    """Operational metadata for a deterministic simulated pipeline run."""

    pipeline_name: str
    run_id: str
    run_date: str
    status: str
    started_at: str
    completed_at: str
    records_read: int
    records_written: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LogEvent:
    """A structured log event produced by the simulated pipeline."""

    timestamp: str
    level: str
    pipeline: str
    component: str
    message: str
    context: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ScenarioManifest:
    """Describes a scenario and the artifacts available to an investigator."""

    scenario_id: str
    description: str
    random_seed: int
    baseline_date: str
    incident_date: str
    artifact_paths: dict[str, list[str]]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class GroundTruth:
    """Evaluation-only expected outcome; never expose this through evidence tools."""

    root_cause: str
    impact: str
    expected_evidence: list[str]
    evaluation: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

