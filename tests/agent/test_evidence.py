"""Phase 3 Plan 3 tests for deterministic evidence provenance helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from investigator.agent.evidence import (
    build_evidence_item,
    build_tool_call_record,
    evidence_id_for_index,
)


def test_evidence_ids_are_stable_and_zero_padded() -> None:
    assert evidence_id_for_index(1) == "E01"
    assert evidence_id_for_index(6) == "E06"
    assert evidence_id_for_index(12) == "E12"


@pytest.mark.parametrize("index", (0, -1))
def test_evidence_ids_reject_non_positive_indexes(index: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        evidence_id_for_index(index)


def test_build_evidence_item_preserves_provenance_and_result() -> None:
    tool_input = {"run_date": "2026-09-02"}
    tool_result = {"run_count": 1, "runs": [{"status": "SUCCESS", "records_written": 150}]}

    evidence = build_evidence_item(
        evidence_id="E01",
        evidence_type="PIPELINE_STATUS",
        source_tool="get_pipeline_status",
        tool_input=tool_input,
        summary="Incident pipeline run succeeded and wrote 150 records.",
        tool_result=tool_result,
    )

    assert evidence.evidence_id == "E01"
    assert evidence.source_tool == "get_pipeline_status"
    assert evidence.tool_input == tool_input
    assert evidence.summary == "Incident pipeline run succeeded and wrote 150 records."
    assert evidence.data == tool_result


def test_build_evidence_item_rejects_unknown_evidence_type() -> None:
    with pytest.raises(ValidationError):
        build_evidence_item(
            evidence_id="E01",
            evidence_type="UNKNOWN",
            source_tool="tool",
            tool_input={},
            summary="Invalid evidence type.",
            tool_result={},
        )


def test_successful_tool_call_record_retains_evidence_id() -> None:
    record = build_tool_call_record(
        tool_name="get_pipeline_status",
        tool_input={"run_date": "2026-09-02"},
        evidence_id="E01",
    )

    assert record.status == "success"
    assert record.evidence_id == "E01"
    assert record.error is None


@pytest.mark.parametrize("error", ("tool unavailable", ""))
def test_failed_tool_call_record_has_no_evidence_id(error: str) -> None:
    record = build_tool_call_record(
        tool_name="get_pipeline_status",
        tool_input={"run_date": "2026-09-02"},
        error=error,
    )

    assert record.status == "error"
    assert record.evidence_id is None
    assert record.error == error


def test_failed_tool_call_record_rejects_evidence_id() -> None:
    with pytest.raises(ValueError, match="cannot reference evidence"):
        build_tool_call_record(
            tool_name="get_pipeline_status",
            tool_input={"run_date": "2026-09-02"},
            evidence_id="E01",
            error="tool unavailable",
        )
