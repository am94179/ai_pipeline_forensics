from operator import add
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from investigator.agent.hypotheses import (
    Hypothesis,
    HypothesisEvaluation,
    InvestigationAction,
)


class IncidentInput(BaseModel):
    incident_id: str
    description: str
    scenario_dir: str
    reported_at: str | None = None


class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: Literal[
        "LOG",
        "SQL_RESULT",
        "PIPELINE_STATUS",
        "DATA_QUALITY_METRIC",
        "STATISTICAL_ANOMALY",
        "CONFIGURATION",
    ]
    source_tool: str
    tool_input: dict[str, object]
    summary: str
    data: dict[str, object]


class ToolCallRecord(BaseModel):
    tool_name: str
    tool_input: dict[str, object]
    status: Literal["success", "error"]
    evidence_id: str | None = None
    error: str | None = None


class EvidenceBackedClaim(BaseModel):
    statement: str
    evidence_ids: list[str] = Field(min_length=1)


class AnalysisResult(BaseModel):
    observations: list[EvidenceBackedClaim] = Field(default_factory=list)
    likely_cause: EvidenceBackedClaim | None = None
    impact: EvidenceBackedClaim | None = None
    limitations: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None


class FinalReport(BaseModel):
    incident_id: str
    summary: str
    findings: list[EvidenceBackedClaim] = Field(default_factory=list)
    likely_cause: EvidenceBackedClaim | None = None
    impact: EvidenceBackedClaim | None = None
    limitations: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    deterministic_evidence: list[EvidenceItem] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    actions_taken: list[InvestigationAction] = Field(default_factory=list)
    termination_reason: str | None = None


class InvestigationState(TypedDict, total=False):
    incident: IncidentInput
    run_id: str
    status: Literal[
        "initialized",
        "gathering_evidence",
        "generating_hypotheses",
        "selecting_action",
        "executing_action",
        "evaluating_hypotheses",
        "analyzing",
        "reported",
        "failed",
    ]
    evidence: Annotated[list[EvidenceItem], add]
    tools_used: Annotated[list[ToolCallRecord], add]
    errors: Annotated[list[str], add]
    analysis: AnalysisResult | None
    final_report: FinalReport | None
    hypotheses: list[Hypothesis]
    actions_taken: Annotated[list[InvestigationAction], add]
    next_action: InvestigationAction | None
    remaining_action_budget: int
    last_evaluation: HypothesisEvaluation | None
    termination_reason: str | None
