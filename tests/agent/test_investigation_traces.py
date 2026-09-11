"""End-to-end, credential-free trace tests for the bounded investigation graph."""

from __future__ import annotations

from pathlib import Path

import pytest

from investigator.agent import hypothesis_nodes
from investigator.agent.graph import build_investigation_graph


class _StructuredResponse:
    def __init__(self, response: object, prompts: list[str]) -> None:
        self.response = response
        self.prompts = prompts

    def invoke(self, prompt: str) -> object:
        self.prompts.append(prompt)
        return self.response


class _ScriptedChatModel:
    def __init__(self, responses: list[object]) -> None:
        self._responses = iter(responses)
        self.prompts: list[str] = []

    def with_structured_output(self, schema: object) -> _StructuredResponse:
        return _StructuredResponse(next(self._responses), self.prompts)


def _state(scenario_id: str) -> dict:
    scenario_dir = Path(__file__).resolve().parents[2] / "data" / "scenarios" / scenario_id
    return {
        "incident": {
            "incident_id": f"{scenario_id}-2026-09-02",
            "description": f"Investigate the {scenario_id} scenario.",
            "scenario_dir": str(scenario_dir),
        }
    }


def _open_hypotheses(statement: str) -> list[dict[str, object]]:
    return [
        {
            "hypothesis_id": "H01",
            "statement": statement,
            "status": "open",
            "confidence": 0.6,
            "supporting_evidence_ids": ["E03"],
            "contradicting_evidence_ids": [],
            "rationale": "The initial evidence shows a downstream volume change.",
        },
        {
            "hypothesis_id": "H02",
            "statement": "A warehouse-load failure caused the observed reduction.",
            "status": "open",
            "confidence": 0.25,
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": [],
            "rationale": "This remains an alternative until targeted evidence is reviewed.",
        },
    ]


@pytest.mark.parametrize(
    ("scenario_id", "cause"),
    [
        ("enum_change", "A source status enum changed"),
        ("null_rate_increase", "Null amount values increased"),
        ("missing_partition", "A source partition was unavailable"),
    ],
)
def test_all_scenarios_produce_a_bounded_auditable_trace(
    scenario_id: str,
    cause: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hypotheses = _open_hypotheses(cause)
    fake_model = _ScriptedChatModel(
        [
            {"hypotheses": hypotheses},
            {
                "action": {
                    "action_id": "A01",
                    "tool_name": "inspect_pipeline_metadata",
                    "tool_input": {},
                    "purpose": "Check configuration relevant to the leading hypothesis.",
                    "target_hypothesis_ids": ["H01"],
                }
            },
            {
                "hypotheses": [
                    {
                        **hypotheses[0],
                        "status": "supported",
                        "confidence": 0.9,
                        "supporting_evidence_ids": ["E03", "E07"],
                    },
                    {
                        **hypotheses[1],
                        "status": "rejected",
                        "contradicting_evidence_ids": ["E07"],
                    },
                ],
                "needs_more_evidence": False,
                "rationale": "The targeted configuration evidence resolves the main uncertainty.",
                "evidence_ids": ["E07"],
            },
        ]
    )
    monkeypatch.setattr(hypothesis_nodes, "build_chat_model", lambda: fake_model)

    result = build_investigation_graph().invoke(_state(scenario_id))
    report = result["final_report"]
    evidence_ids = {item.evidence_id for item in result["evidence"]}

    assert result["termination_reason"] == "hypotheses_evaluated"
    assert len(result["actions_taken"]) == 1
    assert len(result["actions_taken"]) <= 3
    assert len(result["evidence"]) == 7
    assert report.likely_cause.statement == cause
    assert report.likely_cause.evidence_ids == ["E03", "E07"]
    assert report.deterministic_evidence == result["evidence"]
    assert report.hypotheses == result["hypotheses"]
    assert report.actions_taken == result["actions_taken"]
    assert report.termination_reason == "hypotheses_evaluated"
    assert any("not certainty" in limitation for limitation in report.limitations)
    assert all(
        set(hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids)
        <= evidence_ids
        for hypothesis in report.hypotheses
    )
    assert all("ground_truth" not in prompt for prompt in fake_model.prompts)
    assert all(_state(scenario_id)["incident"]["scenario_dir"] not in prompt for prompt in fake_model.prompts)


def test_graph_stops_after_the_three_action_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    hypotheses = _open_hypotheses("The source data may be incomplete.")
    evaluation = lambda evidence_id: {
        "hypotheses": hypotheses,
        "needs_more_evidence": True,
        "rationale": "One more safe check could reduce uncertainty.",
        "evidence_ids": [evidence_id],
    }
    fake_model = _ScriptedChatModel(
        [
            {"hypotheses": hypotheses},
            {"action": _action("A01", "get_pipeline_status", {})},
            evaluation("E07"),
            {"action": _action("A02", "inspect_pipeline_metadata", {})},
            evaluation("E08"),
            {"action": _action("A03", "profile_dataset", {"dataset": "incident_source_orders"})},
            evaluation("E09"),
        ]
    )
    monkeypatch.setattr(hypothesis_nodes, "build_chat_model", lambda: fake_model)

    result = build_investigation_graph().invoke(_state("missing_partition"))

    assert [action.action_id for action in result["actions_taken"]] == ["A01", "A02", "A03"]
    assert result["remaining_action_budget"] == 0
    assert result["termination_reason"] == "action_budget_exhausted"
    assert result["final_report"].termination_reason == "action_budget_exhausted"


def test_graph_keeps_a_partial_trace_after_a_tool_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    hypotheses = _open_hypotheses("Configuration may be responsible.")
    fake_model = _ScriptedChatModel(
        [
            {"hypotheses": hypotheses},
            {"action": _action("A01", "inspect_pipeline_metadata", {})},
            {
                "hypotheses": hypotheses,
                "needs_more_evidence": False,
                "rationale": "The failed action leaves the alternatives unresolved.",
                "evidence_ids": ["E03"],
            },
        ]
    )
    monkeypatch.setattr(hypothesis_nodes, "build_chat_model", lambda: fake_model)
    monkeypatch.setattr(
        hypothesis_nodes,
        "inspect_pipeline_metadata",
        lambda scenario_dir: (_ for _ in ()).throw(RuntimeError("metadata unavailable")),
    )

    result = build_investigation_graph().invoke(_state("null_rate_increase"))

    assert result["status"] == "reported"
    assert result["final_report"].likely_cause is None
    assert result["final_report"].actions_taken[0].action_id == "A01"
    assert any("Action A01 failed" in error for error in result["errors"])
    assert result["final_report"].termination_reason == "hypotheses_evaluated"


def _action(action_id: str, tool_name: str, tool_input: dict[str, object]) -> dict[str, object]:
    return {
        "action_id": action_id,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "purpose": "Resolve a recorded uncertainty.",
        "target_hypothesis_ids": ["H01"],
    }
