"""Phase 3 Plan 2 tests for investigation-state contracts."""

from __future__ import annotations

from operator import add
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from investigator.agent.state import (
    EvidenceBackedClaim,
    EvidenceItem,
    IncidentInput,
    InvestigationState,
    ToolCallRecord,
)


def test_state_models_construct_and_serialize() -> None:
    incident = IncidentInput(
        incident_id="enum-change-2026-09-02",
        description="Revenue reporting output dropped.",
        scenario_dir="data/scenarios/enum_change",
    )
    evidence = EvidenceItem(
        evidence_id="E01",
        evidence_type="PIPELINE_STATUS",
        source_tool="get_pipeline_status",
        tool_input={"run_date": "2026-09-02"},
        summary="The incident pipeline run completed successfully.",
        data={"status": "SUCCESS", "records_written": 150},
    )
    tool_call = ToolCallRecord(
        tool_name="get_pipeline_status",
        tool_input={"run_date": "2026-09-02"},
        status="success",
        evidence_id="E01",
    )

    assert incident.model_dump(mode="json")["incident_id"] == "enum-change-2026-09-02"
    assert evidence.model_dump(mode="json")["data"] == {"status": "SUCCESS", "records_written": 150}
    assert tool_call.model_dump(mode="json")["evidence_id"] == "E01"


def test_state_models_reject_invalid_enum_values() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_id="E01",
            evidence_type="UNKNOWN",
            source_tool="tool",
            tool_input={},
            summary="Invalid type.",
            data={},
        )
    with pytest.raises(ValidationError):
        ToolCallRecord(tool_name="tool", tool_input={}, status="pending")


def test_evidence_backed_claim_requires_at_least_one_citation() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        EvidenceBackedClaim(statement="Output dropped.", evidence_ids=[])


def test_minimal_initial_state_contains_only_incident() -> None:
    incident = IncidentInput(
        incident_id="enum-change-2026-09-02",
        description="Revenue reporting output dropped.",
        scenario_dir="data/scenarios/enum_change",
    )
    state: InvestigationState = {"incident": incident}

    assert state == {"incident": incident}


def test_append_only_state_fields_use_list_concatenation_reducers() -> None:
    hints = get_type_hints(InvestigationState, include_extras=True)

    for field_name in ("evidence", "tools_used", "errors", "actions_taken"):
        metadata = hints[field_name].__metadata__
        assert metadata == (add,)
