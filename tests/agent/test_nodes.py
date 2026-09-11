"""Phase 3 Plan 4 tests for incident initialization."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from uuid import UUID

import pytest

from investigator.agent import nodes
from investigator.agent.state import AnalysisResult, EvidenceBackedClaim, EvidenceItem
from tests.fakes import FakeChatModel, FakeStructuredModel


def test_initialize_incident_returns_clean_normalized_state(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_incident = {
        "incident_id": "enum-change-2026-09-02",
        "description": "Revenue-reporting output dropped.",
        "scenario_dir": str(tmp_path),
    }
    input_state = {"incident": raw_incident}
    original_state = deepcopy(input_state)
    monkeypatch.setattr(nodes, "uuid4", lambda: UUID("12345678-1234-5678-1234-567812345678"))

    result = nodes.initialize_incident(input_state)

    assert result["incident"].incident_id == "enum-change-2026-09-02"
    assert result["run_id"] == "12345678123456781234567812345678"
    assert result["status"] == "initialized"
    assert result["evidence"] == []
    assert result["tools_used"] == []
    assert result["errors"] == []
    assert result["analysis"] is None
    assert result["final_report"] is None
    assert input_state == original_state


def test_initialize_incident_rejects_missing_incident() -> None:
    with pytest.raises(ValueError, match="must include an incident"):
        nodes.initialize_incident({})


def test_initialize_incident_rejects_invalid_incident_dictionary() -> None:
    with pytest.raises(ValueError, match="Invalid incident input"):
        nodes.initialize_incident({"incident": {"incident_id": "only-id"}})


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    (
        ("incident_id", "   ", "Incident ID cannot be blank"),
        ("description", "   ", "Incident description cannot be blank"),
        ("scenario_dir", "   ", "Scenario directory cannot be blank"),
    ),
)
def test_initialize_incident_rejects_blank_required_fields(
    tmp_path, field_name: str, value: str, message: str
) -> None:
    incident = {
        "incident_id": "enum-change-2026-09-02",
        "description": "Revenue-reporting output dropped.",
        "scenario_dir": str(tmp_path),
    }
    incident[field_name] = value

    with pytest.raises(ValueError, match=message):
        nodes.initialize_incident({"incident": incident})


def test_initialize_incident_rejects_missing_scenario_directory(tmp_path) -> None:
    incident = {
        "incident_id": "enum-change-2026-09-02",
        "description": "Revenue-reporting output dropped.",
        "scenario_dir": str(tmp_path / "missing"),
    }

    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        nodes.initialize_incident({"incident": incident})


def test_initialize_incident_rejects_file_as_scenario_directory(tmp_path) -> None:
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("not a scenario", encoding="utf-8")
    incident = {
        "incident_id": "enum-change-2026-09-02",
        "description": "Revenue-reporting output dropped.",
        "scenario_dir": str(file_path),
    }

    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        nodes.initialize_incident({"incident": incident})


def _enum_change_state() -> dict:
    scenario_dir = Path(__file__).resolve().parents[2] / "data/scenarios/enum_change"
    return {
        "incident": {
            "incident_id": "enum-change-2026-09-02",
            "description": "Revenue-reporting output dropped.",
            "scenario_dir": str(scenario_dir),
        }
    }


def test_gather_initial_evidence_returns_fixed_six_item_bundle() -> None:
    input_state = _enum_change_state()
    original_state = deepcopy(input_state)

    result = nodes.gather_initial_evidence(input_state)

    assert result["status"] == "gathering_evidence"
    assert [item.evidence_id for item in result["evidence"]] == [
        "E01",
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
    ]
    assert [item.evidence_type for item in result["evidence"]] == [
        "PIPELINE_STATUS",
        "STATISTICAL_ANOMALY",
        "DATA_QUALITY_METRIC",
        "DATA_QUALITY_METRIC",
        "CONFIGURATION",
        "LOG",
    ]
    assert [item.source_tool for item in result["evidence"]] == [
        "get_pipeline_status",
        "compare_distributions",
        "compare_distributions",
        "profile_dataset",
        "inspect_pipeline_metadata",
        "search_logs",
    ]
    assert result["evidence"][1].tool_input["baseline_dataset"] == "baseline_source_orders"
    assert result["evidence"][2].tool_input["incident_dataset"] == (
        "incident_warehouse_orders"
    )
    assert result["errors"] == []
    assert [call.status for call in result["tools_used"]] == ["success"] * 6
    assert [call.evidence_id for call in result["tools_used"]] == [
        "E01",
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
    ]
    assert input_state == original_state


def test_gather_initial_evidence_continues_after_source_comparison_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_compare_distributions = nodes.compare_distributions

    def fail_source_comparison(scenario_dir: Path, **tool_input: object) -> dict[str, object]:
        if tool_input["baseline_dataset"] == "baseline_source_orders":
            raise RuntimeError("source fixture unavailable")
        return original_compare_distributions(scenario_dir, **tool_input)

    monkeypatch.setattr(nodes, "compare_distributions", fail_source_comparison)

    result = nodes.gather_initial_evidence(_enum_change_state())

    assert [item.evidence_id for item in result["evidence"]] == [
        "E01",
        "E03",
        "E04",
        "E05",
        "E06",
    ]
    assert len(result["tools_used"]) == 6
    failed_call = result["tools_used"][1]
    assert failed_call.tool_name == "compare_distributions"
    assert failed_call.status == "error"
    assert failed_call.evidence_id is None
    assert "source fixture unavailable" in failed_call.error
    assert result["errors"] == [
        "source compare_distributions failed: source fixture unavailable"
    ]



def test_analyze_evidence_returns_structured_fake_model_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = {
        "observations": [
            {
                "statement": "The pipeline status evidence was collected.",
                "evidence_ids": ["E01"],
            }
        ],
        "likely_cause": {
            "statement": "The configuration requires investigation.",
            "evidence_ids": ["E01"],
        },
        "limitations": ["Only one evidence item was supplied to the fake model."],
        "recommended_next_action": "Review the pipeline configuration.",
    }
    structured_model = FakeStructuredModel(response)
    fake_model = FakeChatModel(structured_model)
    monkeypatch.setattr(nodes, "build_chat_model", lambda: fake_model)
    input_state = _enum_change_state()
    input_state["evidence"] = [
        EvidenceItem(
            evidence_id="E01",
            evidence_type="PIPELINE_STATUS",
            source_tool="get_pipeline_status",
            tool_input={},
            summary="Retrieved pipeline status.",
            data={"run_count": 2},
        )
    ]
    input_state["errors"] = ["search_logs failed: unavailable"]

    result = nodes.analyze_evidence(input_state)

    assert result["status"] == "analyzing"
    assert isinstance(result["analysis"], AnalysisResult)
    assert result["analysis"].likely_cause.evidence_ids == ["E01"]
    assert fake_model.output_schema is AnalysisResult
    assert len(structured_model.prompts) == 1
    prompt = structured_model.prompts[0]
    assert "E01" in prompt
    assert "search_logs failed: unavailable" in prompt
    assert "scenario_dir" not in prompt
    assert input_state["incident"]["scenario_dir"] not in prompt
    assert "ground_truth" not in prompt


def test_analyze_evidence_records_model_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeChatModel(FakeStructuredModel(RuntimeError("model unavailable")))
    monkeypatch.setattr(nodes, "build_chat_model", lambda: fake_model)

    result = nodes.analyze_evidence(_enum_change_state())

    assert result == {
        "status": "failed",
        "analysis": None,
        "errors": ["LLM analysis failed (RuntimeError)."],
    }


def test_generate_final_report_returns_reported_state() -> None:
    input_state = _enum_change_state()
    input_state["evidence"] = [
        EvidenceItem(
            evidence_id="E01",
            evidence_type="PIPELINE_STATUS",
            source_tool="get_pipeline_status",
            tool_input={},
            summary="Retrieved pipeline status.",
            data={},
        )
    ]
    input_state["analysis"] = AnalysisResult(
        observations=[
            EvidenceBackedClaim(
                statement="The pipeline status was collected.", evidence_ids=["E01"]
            )
        ],
        likely_cause=EvidenceBackedClaim(
            statement="The cause requires further investigation.", evidence_ids=["E01"]
        ),
    )

    result = nodes.generate_final_report(input_state)

    assert result["status"] == "reported"
    assert result["final_report"].incident_id == "enum-change-2026-09-02"
    assert result["final_report"].findings == input_state["analysis"].observations
    assert result["final_report"].likely_cause == input_state["analysis"].likely_cause
    assert result["errors"] == []


def test_generate_final_report_omits_invalid_citations() -> None:
    input_state = _enum_change_state()
    input_state["evidence"] = [
        EvidenceItem(
            evidence_id="E01",
            evidence_type="PIPELINE_STATUS",
            source_tool="get_pipeline_status",
            tool_input={},
            summary="Retrieved pipeline status.",
            data={},
        )
    ]
    input_state["analysis"] = AnalysisResult(
        likely_cause=EvidenceBackedClaim(
            statement="Unsupported cause.", evidence_ids=["E99"]
        )
    )

    result = nodes.generate_final_report(input_state)

    assert result["final_report"].likely_cause is None
    assert result["errors"] == [
        "Omitted likely cause with unknown evidence IDs: E99."
    ]


def test_generate_final_report_creates_partial_report_after_analysis_failure() -> None:
    input_state = _enum_change_state()
    input_state["errors"] = ["LLM analysis failed (RuntimeError)."]

    result = nodes.generate_final_report(input_state)

    assert result["status"] == "reported"
    assert result["final_report"].likely_cause is None
    assert "analysis was unavailable" in result["final_report"].summary
    assert "LLM analysis failed (RuntimeError)." in result["final_report"].limitations
    assert result["errors"] == []
