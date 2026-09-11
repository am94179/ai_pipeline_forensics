"""Hypothesis and action contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from investigator.agent.hypotheses import (
    Hypothesis,
    HypothesisEvaluation,
    InvestigationAction,
)


def _open_hypothesis() -> Hypothesis:
    return Hypothesis(
        hypothesis_id="H01",
        statement="A transformation filter excluded valid records.",
        confidence=0.4,
        rationale="Initial evidence does not yet distinguish this from an ingestion issue.",
    )


def test_hypothesis_contract_serializes_supported_evidence() -> None:
    hypothesis = Hypothesis(
        hypothesis_id="H01",
        statement="A transformation filter excluded valid records.",
        status="supported",
        confidence=0.85,
        supporting_evidence_ids=["E03", "E05"],
        rationale="Warehouse volume declined and configuration contains the filter.",
    )

    assert hypothesis.model_dump(mode="json")["supporting_evidence_ids"] == ["E03", "E05"]


@pytest.mark.parametrize("status", ("unknown", "confirmed"))
def test_hypothesis_rejects_invalid_status(status: str) -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            hypothesis_id="H01",
            statement="Invalid status.",
            status=status,
            confidence=0.5,
            rationale="Invalid status should fail validation.",
        )


def test_hypothesis_requires_evidence_for_supported_or_rejected_status() -> None:
    with pytest.raises(ValidationError, match="Supported hypotheses require"):
        Hypothesis(
            hypothesis_id="H01",
            statement="Unsupported supported hypothesis.",
            status="supported",
            confidence=0.8,
            rationale="Missing evidence IDs.",
        )
    with pytest.raises(ValidationError, match="Rejected hypotheses require"):
        Hypothesis(
            hypothesis_id="H02",
            statement="Unsupported rejected hypothesis.",
            status="rejected",
            confidence=0.1,
            rationale="Missing evidence IDs.",
        )


def test_action_rejects_unsupported_tool_and_malformed_inputs() -> None:
    with pytest.raises(ValidationError):
        InvestigationAction(
            action_id="A01",
            tool_name="delete_data",
            tool_input={},
            purpose="Unsafe action.",
            target_hypothesis_ids=["H01"],
        )
    with pytest.raises(ValidationError):
        InvestigationAction(
            action_id="A02",
            tool_name="search_logs",
            tool_input=["not", "a", "mapping"],
            purpose="Malformed tool input.",
            target_hypothesis_ids=["H01"],
        )


def test_hypothesis_evaluation_requires_cited_evidence() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        HypothesisEvaluation(
            hypotheses=[_open_hypothesis()],
            needs_more_evidence=True,
            rationale="More evidence is needed.",
            evidence_ids=[],
        )
