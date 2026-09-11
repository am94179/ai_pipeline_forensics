from investigator.agent.state import EvidenceItem, ToolCallRecord


def evidence_id_for_index(index: int) -> str:
    if index < 1:
        raise ValueError("Evidence index must be at least 1.")

    return f"E{index:02d}"


def build_evidence_item(
    *,
    evidence_id: str,
    evidence_type: str,
    source_tool: str,
    tool_input: dict[str, object],
    summary: str,
    tool_result: dict[str, object],
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source_tool=source_tool,
        tool_input=tool_input,
        summary=summary,
        data=tool_result,
    )


def build_tool_call_record(
    *,
    tool_name: str,
    tool_input: dict[str, object],
    evidence_id: str | None = None,
    error: str | None = None,
) -> ToolCallRecord:
    """Record either a successful or failed tool invocation."""
    status = "error" if error is not None else "success"

    if error is not None and evidence_id is not None:
        raise ValueError("Failed tool calls cannot reference evidence.")

    return ToolCallRecord(
        tool_name=tool_name,
        tool_input=tool_input,
        status=status,
        evidence_id=evidence_id,
        error=error,
    )
