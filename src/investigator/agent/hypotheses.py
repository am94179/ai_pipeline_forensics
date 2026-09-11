"""Structured contracts for bounded hypothesis-based investigations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


HypothesisStatus = Literal["open", "supported", "rejected", "inconclusive"]
AllowedActionTool = Literal[
    "search_logs",
    "profile_dataset",
    "compare_distributions",
    "get_pipeline_status",
    "inspect_pipeline_metadata",
    "inspect_schema",
    "query_data",
]


class Hypothesis(BaseModel):
    """One plausible explanation tracked during an investigation."""

    hypothesis_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    status: HypothesisStatus = "open"
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @field_validator("supporting_evidence_ids", "contradicting_evidence_ids")
    @classmethod
    def evidence_ids_cannot_be_blank(cls, evidence_ids: list[str]) -> list[str]:
        if any(not evidence_id.strip() for evidence_id in evidence_ids):
            raise ValueError("Evidence IDs cannot be blank.")
        return evidence_ids

    @model_validator(mode="after")
    def validate_status_evidence(self) -> "Hypothesis":
        if self.status == "supported" and not self.supporting_evidence_ids:
            raise ValueError("Supported hypotheses require supporting evidence IDs.")
        if self.status == "rejected" and not self.contradicting_evidence_ids:
            raise ValueError("Rejected hypotheses require contradicting evidence IDs.")
        overlap = set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids)
        if overlap:
            raise ValueError("Evidence cannot both support and contradict one hypothesis.")
        return self


class InvestigationAction(BaseModel):
    """One validated, targeted request to an existing deterministic tool."""

    action_id: str = Field(min_length=1)
    tool_name: AllowedActionTool
    tool_input: dict[str, object] = Field(default_factory=dict)
    purpose: str = Field(min_length=1)
    target_hypothesis_ids: list[str] = Field(min_length=1)

    @field_validator("target_hypothesis_ids")
    @classmethod
    def target_hypothesis_ids_cannot_be_blank(cls, hypothesis_ids: list[str]) -> list[str]:
        if any(not hypothesis_id.strip() for hypothesis_id in hypothesis_ids):
            raise ValueError("Target hypothesis IDs cannot be blank.")
        return hypothesis_ids


class HypothesisEvaluation(BaseModel):
    """One evidence-cited update to the current set of hypotheses."""

    hypotheses: list[Hypothesis] = Field(min_length=1)
    needs_more_evidence: bool
    rationale: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_ids_cannot_be_blank(cls, evidence_ids: list[str]) -> list[str]:
        if any(not evidence_id.strip() for evidence_id in evidence_ids):
            raise ValueError("Evidence IDs cannot be blank.")
        return evidence_ids
