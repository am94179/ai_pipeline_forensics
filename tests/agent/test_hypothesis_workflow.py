"""Focused tests for the bounded hypothesis investigation loop."""

from __future__ import annotations

from pathlib import Path

import pytest

from investigator.agent import hypothesis_nodes
from investigator.agent.graph import build_investigation_graph
from investigator.agent.hypotheses import Hypothesis, InvestigationAction
from investigator.agent.planning import ActionDecision, HypothesisSet, validate_action
from investigator.agent.state import EvidenceItem


class _SequenceStructuredModel:
    def __init__(self, response: object) -> None:
        self.response = response
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> object:
        self.prompts.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _SequenceChatModel:
    def __init__(self, responses: list[object]) -> None:
        self.responses = iter(responses)
        self.schemas: list[object] = []

    def with_structured_output(self, schema: object) -> _SequenceStructuredModel:
        self.schemas.append(schema)
        return _SequenceStructuredModel(next(self.responses))


def _state() -> dict:
    scenario_dir = Path(__file__).resolve().parents[2] / "data/scenarios/enum_change"
    return {
        "incident": {
            "incident_id": "enum-change-2026-09-02",
            "description": "Revenue-reporting output dropped.",
            "scenario_dir": str(scenario_dir),
        }
    }


def _hypotheses() -> list[dict[str, object]]:
    return [
        {
            "hypothesis_id": "H01",
            "statement": "A source status value changed and bypassed the completed-order filter.",
            "status": "open",
            "confidence": 0.6,
            "supporting_evidence_ids": ["E02"],
            "contradicting_evidence_ids": [],
            "rationale": "The source distribution changed.",
        },
        {
            "hypothesis_id": "H02",
            "statement": "The warehouse load failed after transformation.",
            "status": "open",
            "confidence": 0.3,
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": [],
            "rationale": "The output decrease needs confirmation.",
        },
    ]


def test_validate_action_rejects_duplicate_and_unsafe_requests() -> None:
    action = InvestigationAction(
        action_id="A01",
        tool_name="profile_dataset",
        tool_input={"dataset": "incident_source_orders"},
        purpose="Measure source null rates.",
        target_hypothesis_ids=["H01"],
    )
    validate_action(action, known_hypothesis_ids={"H01"}, previous_actions=[])

    with pytest.raises(ValueError, match="already used"):
        validate_action(action, known_hypothesis_ids={"H01"}, previous_actions=[action])

    unsafe = action.model_copy(update={"action_id": "A02", "tool_input": {"path": "ground_truth/ground_truth.json"}})
    with pytest.raises(ValueError, match="Unsupported input"):
        validate_action(unsafe, known_hypothesis_ids={"H01"}, previous_actions=[])


def test_execute_action_adds_unique_evidence_and_consumes_budget() -> None:
    state = _state()
    state.update(
        {
            "evidence": [
                EvidenceItem(
                    evidence_id="E01",
                    evidence_type="PIPELINE_STATUS",
                    source_tool="get_pipeline_status",
                    tool_input={},
                    summary="Existing evidence.",
                    data={},
                ),
                EvidenceItem(
                    evidence_id="E03",
                    evidence_type="DATA_QUALITY_METRIC",
                    source_tool="compare_distributions",
                    tool_input={},
                    summary="Existing evidence.",
                    data={},
                ),
            ],
            "hypotheses": [Hypothesis.model_validate(item) for item in _hypotheses()],
            "actions_taken": [],
            "remaining_action_budget": 3,
            "next_action": InvestigationAction(
                action_id="A01",
                tool_name="get_pipeline_status",
                tool_input={},
                purpose="Confirm pipeline completion.",
                target_hypothesis_ids=["H02"],
            ),
        }
    )

    result = hypothesis_nodes.execute_action(state)

    assert result["evidence"][0].evidence_id == "E04"
    assert result["tools_used"][0].status == "success"
    assert result["actions_taken"][0].action_id == "A01"
    assert result["remaining_action_budget"] == 2


def test_graph_runs_one_bounded_action_and_reports_supported_hypothesis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = _SequenceChatModel(
        [
            {"hypotheses": _hypotheses()},
            {
                "action": {
                    "action_id": "A01",
                    "tool_name": "search_logs",
                    "tool_input": {"query": "enum", "component": "transformation"},
                    "purpose": "Confirm whether the transformation logged an enum mismatch.",
                    "target_hypothesis_ids": ["H01"],
                }
            },
            {
                "hypotheses": [
                    {
                        **_hypotheses()[0],
                        "status": "supported",
                        "confidence": 0.9,
                        "supporting_evidence_ids": ["E02", "E07"],
                    },
                    {**_hypotheses()[1], "status": "rejected", "contradicting_evidence_ids": ["E07"]},
                ],
                "needs_more_evidence": False,
                "rationale": "The log directly records the enum mismatch.",
                "evidence_ids": ["E07"],
            },
        ]
    )
    monkeypatch.setattr(hypothesis_nodes, "build_chat_model", lambda: fake_model)

    result = build_investigation_graph().invoke(_state())

    assert result["status"] == "reported"
    assert [action.action_id for action in result["actions_taken"]] == ["A01"]
    assert result["remaining_action_budget"] == 2
    assert result["evidence"][-1].evidence_id == "E07"
    assert result["final_report"].likely_cause.evidence_ids == ["E02", "E07"]
    assert "ground_truth" not in "\n".join(
        prompt for schema in fake_model.schemas for prompt in []
    )


def test_selector_rejects_invalid_action_before_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_model = _SequenceChatModel(
        [
            {
                "action": {
                    "action_id": "A01",
                    "tool_name": "profile_dataset",
                    "tool_input": {"dataset": "ground_truth"},
                    "purpose": "Read hidden ground truth.",
                    "target_hypothesis_ids": ["H01"],
                }
            }
        ]
    )
    monkeypatch.setattr(hypothesis_nodes, "build_chat_model", lambda: fake_model)
    state = _state()
    state.update({"hypotheses": [Hypothesis.model_validate(item) for item in _hypotheses()], "actions_taken": [], "remaining_action_budget": 3})

    result = hypothesis_nodes.select_next_action(state)

    assert result["next_action"] is None
    assert result["termination_reason"] == "action_selection_failed"
    assert result["errors"] == ["Action selection failed (ValueError)."]
