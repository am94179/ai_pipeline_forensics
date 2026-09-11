"""Credential-free coverage for the optional investigator workflow candidate."""

from __future__ import annotations

from pathlib import Path

import pytest

from investigator.agent import hypothesis_nodes
from investigator.agent.hypotheses import HypothesisEvaluation
from investigator.agent.planning import ActionDecision, HypothesisSet
from investigator.evaluation.runner import INVESTIGATOR_WORKFLOW_CANDIDATE, run_evaluation


class _WorkflowFakeModel:
    def __init__(self) -> None:
        self.schema: object | None = None

    def with_structured_output(self, schema: object) -> "_WorkflowFakeModel":
        self.schema = schema
        return self

    def invoke(self, prompt: str) -> object:
        if self.schema is HypothesisSet:
            return {"hypotheses": _hypotheses()}
        if self.schema is ActionDecision:
            return {
                "action": {
                    "action_id": "A01",
                    "tool_name": "inspect_pipeline_metadata",
                    "tool_input": {},
                    "purpose": "Review public pipeline configuration.",
                    "target_hypothesis_ids": ["H01"],
                }
            }
        if self.schema is HypothesisEvaluation:
            return {
                "hypotheses": [
                    {
                        **_hypotheses()[0],
                        "status": "supported",
                        "confidence": 0.8,
                        "supporting_evidence_ids": ["E03", "E07"],
                    },
                    {
                        **_hypotheses()[1],
                        "status": "rejected",
                        "contradicting_evidence_ids": ["E07"],
                    },
                ],
                "needs_more_evidence": False,
                "rationale": "The follow-up configuration evidence resolved the uncertainty.",
                "evidence_ids": ["E07"],
            }
        raise AssertionError(f"Unexpected schema: {self.schema}")


def test_investigator_workflow_candidate_runs_with_a_fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    scenarios_root = Path(__file__).resolve().parents[2] / "data" / "scenarios"
    monkeypatch.setattr(hypothesis_nodes, "build_chat_model", _WorkflowFakeModel)

    report = run_evaluation(candidate_name=INVESTIGATOR_WORKFLOW_CANDIDATE, scenarios_root=scenarios_root)

    assert report.candidate_name == INVESTIGATOR_WORKFLOW_CANDIDATE
    assert report.aggregate["scenario_count"] == 3
    assert report.aggregate["mean_additional_actions"] == 1.0
    assert report.aggregate["citation_validity_rate"] == 1.0


def _hypotheses() -> list[dict[str, object]]:
    return [
        {
            "hypothesis_id": "H01",
            "statement": "A public evidence issue caused the downstream reduction.",
            "status": "open",
            "confidence": 0.6,
            "supporting_evidence_ids": ["E03"],
            "contradicting_evidence_ids": [],
            "rationale": "The downstream volume changed.",
        },
        {
            "hypothesis_id": "H02",
            "statement": "A warehouse failure caused the downstream reduction.",
            "status": "open",
            "confidence": 0.2,
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": [],
            "rationale": "This remains an alternative.",
        },
    ]
