"""Serializable contracts for local, evaluation-only scoring."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from investigator.agent.state import FinalReport


class EvaluationCase(BaseModel):
    """Expected behavior for one scenario; loaded only by evaluation code."""

    scenario_id: str = Field(min_length=1)
    root_cause_label: str = Field(min_length=1)
    accepted_keywords: list[str] = Field(min_length=1)
    required_evidence_ids: list[str] = Field(min_length=1)
    allowed_ambiguity: list[str] = Field(default_factory=list)

    @field_validator("accepted_keywords", "required_evidence_ids")
    @classmethod
    def values_must_be_nonblank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("Evaluation values cannot be blank.")
        if len(values) != len(set(values)):
            raise ValueError("Evaluation values must be distinct.")
        return values


class EvaluationOutcome(BaseModel):
    """One normalized candidate result that can be scored without rerunning it."""

    scenario_id: str = Field(min_length=1)
    candidate_name: str = Field(min_length=1)
    final_report: FinalReport
    tool_call_count: int = Field(ge=0)
    graph_step_count: int | None = Field(default=None, ge=0)
    elapsed_seconds: float | None = Field(default=None, ge=0.0)
    provider_cost_usd: float | None = Field(default=None, ge=0.0)


class ScenarioScore(BaseModel):
    """Transparent metric results for one candidate/scenario pair."""

    scenario_id: str
    candidate_name: str
    root_cause_match: bool
    diagnosis_status: Literal["correct", "ambiguous", "no_diagnosis", "incorrect"]
    required_evidence_present: bool
    citations_valid: bool
    hypothesis_trace_valid: bool
    false_positive: bool
    additional_actions: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    termination_reason: str | None = None
    reasons: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    """A stable, machine-readable local evaluation result."""

    candidate_name: str
    scores: list[ScenarioScore]
    aggregate: dict[str, float | int]
    limitations: list[str] = Field(default_factory=list)
