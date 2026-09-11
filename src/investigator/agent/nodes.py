import logging

from investigator.agent.state import AnalysisResult, IncidentInput, InvestigationState
from uuid import uuid4
from pathlib import Path
from investigator.tools import (
    compare_distributions,
    inspect_pipeline_metadata,
    get_pipeline_status,
    search_logs,
    profile_dataset,
)
from investigator.agent.evidence import (
    build_evidence_item,
    build_tool_call_record,
    evidence_id_for_index,
)
from investigator.llm.prompts import build_analysis_prompt
from investigator.llm.provider import build_chat_model
from investigator.reporting.report import build_final_report
from pydantic import ValidationError

logger = logging.getLogger(__name__)


def _validated_incident(state: InvestigationState) -> IncidentInput:
    raw_incident = state.get("incident")

    if raw_incident is None:
        raise ValueError("Investigation state must include an incident.")

    try:
        incident = IncidentInput.model_validate(raw_incident)
    except ValidationError as error:
        raise ValueError(f"Invalid incident input: {error}") from error

    if not incident.incident_id.strip():
        raise ValueError("Incident ID cannot be blank.")

    if not incident.description.strip():
        raise ValueError("Incident description cannot be blank.")

    if not incident.scenario_dir.strip():
        raise ValueError("Scenario directory cannot be blank.")

    if not Path(incident.scenario_dir).is_dir():
        raise ValueError(
            f"Scenario directory does not exist or is not a directory: "
            f"{incident.scenario_dir}"
        )

    return incident


def initialize_incident(state: InvestigationState) -> dict:
    incident = _validated_incident(state)
    return {
        "incident": incident,
        "run_id": uuid4().hex,
        "status": "initialized",
        "evidence": [],
        "tools_used": [],
        "analysis": None,
        "final_report": None,
        "errors": [],
        "hypotheses": [],
        "actions_taken": [],
        "next_action": None,
        "remaining_action_budget": 3,
        "last_evaluation": None,
        "termination_reason": None,
    }


def gather_initial_evidence(state: InvestigationState) -> dict:
    """Gather the fixed Phase 2 evidence bundle without reading ground truth."""
    incident = _validated_incident(state)
    scenario_dir = Path(incident.scenario_dir)
    run_id = state.get("run_id", "unknown")
    logger.info("Run %s started evidence gathering.", run_id)
    evidence = []
    tool_calls = []
    errors = []

    # E01 - Pipeline status
    try:
        pipeline_status = get_pipeline_status(scenario_dir)
        item = build_evidence_item(
            evidence_id=evidence_id_for_index(1),
            evidence_type="PIPELINE_STATUS",
            source_tool="get_pipeline_status",
            tool_input={},
            summary="Retrieved pipeline run status and row-count metadata for the scenario.",
            tool_result=pipeline_status,
        )
        evidence.append(item)
        tool_calls.append(
            build_tool_call_record(
                tool_name="get_pipeline_status", tool_input={}, evidence_id=item.evidence_id
            )
        )
    except Exception as error:
        message = f"get_pipeline_status failed: {error}"
        errors.append(message)
        tool_calls.append(
            build_tool_call_record(
                tool_name="get_pipeline_status", tool_input={}, error=message
            )
        )

    # E02 - Source distribution comparison
    source_tool_input = {
        "baseline_dataset": "baseline_source_orders",
        "incident_dataset": "incident_source_orders",
        "categorical_columns": ["order_status"],
    }
    try:
        source_comparison = compare_distributions(scenario_dir, **source_tool_input)
        item = build_evidence_item(
            evidence_id=evidence_id_for_index(2),
            evidence_type="STATISTICAL_ANOMALY",
            source_tool="compare_distributions",
            tool_input=source_tool_input,
            summary="Compared source order-status distributions between baseline and incident runs.",
            tool_result=source_comparison,
        )
        evidence.append(item)
        tool_calls.append(
            build_tool_call_record(
                tool_name="compare_distributions",
                tool_input=source_tool_input,
                evidence_id=item.evidence_id,
            )
        )
    except Exception as error:
        message = f"source compare_distributions failed: {error}"
        errors.append(message)
        tool_calls.append(
            build_tool_call_record(
                tool_name="compare_distributions", tool_input=source_tool_input, error=message
            )
        )

    # E03 - Warehouse distribution comparison
    warehouse_tool_input = {
        "baseline_dataset": "baseline_warehouse_orders",
        "incident_dataset": "incident_warehouse_orders",
        "categorical_columns": ["order_status"],
    }
    try:
        warehouse_comparison = compare_distributions(scenario_dir, **warehouse_tool_input)
        item = build_evidence_item(
            evidence_id=evidence_id_for_index(3),
            evidence_type="DATA_QUALITY_METRIC",
            source_tool="compare_distributions",
            tool_input=warehouse_tool_input,
            summary="Compared warehouse order-status distributions and row counts between baseline and incident runs.",
            tool_result=warehouse_comparison,
        )
        evidence.append(item)
        tool_calls.append(
            build_tool_call_record(
                tool_name="compare_distributions",
                tool_input=warehouse_tool_input,
                evidence_id=item.evidence_id,
            )
        )
    except Exception as error:
        message = f"warehouse compare_distributions failed: {error}"
        errors.append(message)
        tool_calls.append(
            build_tool_call_record(
                tool_name="compare_distributions", tool_input=warehouse_tool_input, error=message
            )
        )

    # E04 - Incident source profile
    incident_source_profile_tool_input = {
        "dataset": "incident_source_orders",
        "categorical_columns": ["order_status"],
    }
    try:
        incident_source_profile = profile_dataset(
            scenario_dir, **incident_source_profile_tool_input
        )
        item = build_evidence_item(
            evidence_id=evidence_id_for_index(4),
            evidence_type="DATA_QUALITY_METRIC",
            source_tool="profile_dataset",
            tool_input=incident_source_profile_tool_input,
            summary="Profiled the incident source order_status distribution.",
            tool_result=incident_source_profile,
        )
        evidence.append(item)
        tool_calls.append(
            build_tool_call_record(
                tool_name="profile_dataset",
                tool_input=incident_source_profile_tool_input,
                evidence_id=item.evidence_id,
            )
        )
    except Exception as error:
        message = f"profile_dataset failed: {error}"
        errors.append(message)
        tool_calls.append(
            build_tool_call_record(
                tool_name="profile_dataset",
                tool_input=incident_source_profile_tool_input,
                error=message,
            )
        )

    # E05 - Pipeline configuration
    try:
        pipeline_metadata = inspect_pipeline_metadata(scenario_dir)
        item = build_evidence_item(
            evidence_id=evidence_id_for_index(5),
            evidence_type="CONFIGURATION",
            source_tool="inspect_pipeline_metadata",
            tool_input={},
            summary="Retrieved the pipeline configuration metadata.",
            tool_result=pipeline_metadata,
        )
        evidence.append(item)
        tool_calls.append(
            build_tool_call_record(
                tool_name="inspect_pipeline_metadata",
                tool_input={},
                evidence_id=item.evidence_id,
            )
        )
    except Exception as error:
        message = f"inspect_pipeline_metadata failed: {error}"
        errors.append(message)
        tool_calls.append(
            build_tool_call_record(
                tool_name="inspect_pipeline_metadata", tool_input={}, error=message
            )
        )

    # E06 - Relevant transformation logs
    log_tool_input = {"query": "completed-order", "component": "transformation"}
    try:
        log_results = search_logs(scenario_dir, **log_tool_input)
        item = build_evidence_item(
            evidence_id=evidence_id_for_index(6),
            evidence_type="LOG",
            source_tool="search_logs",
            tool_input=log_tool_input,
            summary="Retrieved transformation log events matching the completed-order query.",
            tool_result=log_results,
        )
        evidence.append(item)
        tool_calls.append(
            build_tool_call_record(
                tool_name="search_logs", tool_input=log_tool_input, evidence_id=item.evidence_id
            )
        )
    except Exception as error:
        message = f"search_logs failed: {error}"
        errors.append(message)
        tool_calls.append(
            build_tool_call_record(
                tool_name="search_logs", tool_input=log_tool_input, error=message
            )
        )

    for tool_call in tool_calls:
        if tool_call.status == "success":
            logger.info(
                "Run %s gathered evidence %s with %s.",
                run_id,
                tool_call.evidence_id,
                tool_call.tool_name,
            )
        else:
            logger.warning(
                "Run %s failed tool %s: %s",
                run_id,
                tool_call.tool_name,
                tool_call.error,
            )
    logger.info("Run %s completed evidence gathering with %d item(s).", run_id, len(evidence))

    return {
        "status": "gathering_evidence",
        "evidence": evidence,
        "tools_used": tool_calls,
        "errors": errors,
    }


def analyze_evidence(state: InvestigationState) -> dict:
    """Analyze collected evidence with the configured LLM and structured output."""
    incident = _validated_incident(state)
    evidence = state.get("evidence", [])
    gathering_errors = state.get("errors", [])
    run_id = state.get("run_id", "unknown")
    logger.info("Run %s started evidence analysis.", run_id)
    prompt = build_analysis_prompt(
        incident=incident,
        evidence=evidence,
        gathering_errors=gathering_errors,
    )

    try:
        model = build_chat_model()
        structured_model = model.with_structured_output(AnalysisResult)
        response = structured_model.invoke(prompt)
        analysis = AnalysisResult.model_validate(response)
    except Exception as error:
        logger.warning("Run %s LLM analysis failed (%s).", run_id, type(error).__name__)
        return {
            "status": "failed",
            "analysis": None,
            "errors": [f"LLM analysis failed ({type(error).__name__})."],
        }

    logger.info("Run %s completed evidence analysis.", run_id)

    return {
        "status": "analyzing",
        "analysis": analysis,
    }


def generate_final_report(state: InvestigationState) -> dict:
    """Create a citation-validated final report without invoking tools or an LLM."""
    incident = _validated_incident(state)
    evidence = state.get("evidence", [])
    available_evidence_ids = {item.evidence_id for item in evidence}
    run_id = state.get("run_id", "unknown")
    logger.info("Run %s started final-report generation.", run_id)
    report, validation_errors = build_final_report(
        incident=incident,
        analysis=state.get("analysis"),
        available_evidence_ids=available_evidence_ids,
        prior_errors=state.get("errors", []),
    )
    if validation_errors:
        logger.warning(
            "Run %s omitted %d claim(s) with invalid citations.",
            run_id,
            len(validation_errors),
        )
    logger.info("Run %s generated final report.", run_id)

    return {
        "status": "reported",
        "final_report": report,
        "errors": validation_errors,
    }
