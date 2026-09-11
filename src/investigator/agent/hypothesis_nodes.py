"""Small nodes for the bounded hypothesis investigation loop."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from investigator.agent.evidence import build_evidence_item, build_tool_call_record
from investigator.agent.hypotheses import HypothesisEvaluation, InvestigationAction
from investigator.agent.nodes import _validated_incident
from investigator.agent.planning import ActionDecision, HypothesisSet, validate_action
from investigator.agent.state import AnalysisResult, EvidenceBackedClaim, InvestigationState
from investigator.llm.hypothesis_prompts import (
    build_action_prompt,
    build_evaluation_prompt,
    build_hypothesis_prompt,
)
from investigator.llm.provider import build_chat_model
from investigator.reporting.report import build_final_report
from investigator.reporting.trace import attach_investigation_trace
from investigator.tools import (
    compare_distributions,
    get_pipeline_status,
    inspect_pipeline_metadata,
    profile_dataset,
    search_logs,
)


DEFAULT_ACTION_BUDGET = 3


def generate_hypotheses(state: InvestigationState) -> dict:
    """Use the LLM once to propose a small, evidence-cited alternative set."""
    incident = _validated_incident(state)
    evidence = state.get("evidence", [])
    try:
        model = build_chat_model().with_structured_output(HypothesisSet)
        response = HypothesisSet.model_validate(
            model.invoke(build_hypothesis_prompt(incident=incident, evidence=evidence, errors=state.get("errors", [])))
        )
        _validate_hypothesis_citations(response.hypotheses, {item.evidence_id for item in evidence})
    except Exception as error:
        return {
            "status": "failed",
            "hypotheses": [],
            "termination_reason": "hypothesis_generation_failed",
            "errors": [f"Hypothesis generation failed ({type(error).__name__})."],
        }
    return {
        "status": "generating_hypotheses",
        "hypotheses": response.hypotheses,
        "remaining_action_budget": state.get("remaining_action_budget", DEFAULT_ACTION_BUDGET),
    }


def select_next_action(state: InvestigationState) -> dict:
    """Select one validated action, or finish before any tool is executed."""
    hypotheses = state.get("hypotheses", [])
    budget = state.get("remaining_action_budget", DEFAULT_ACTION_BUDGET)
    if not hypotheses:
        return {"status": "selecting_action", "next_action": None, "termination_reason": "no_hypotheses"}
    if budget <= 0:
        return {"status": "selecting_action", "next_action": None, "termination_reason": "action_budget_exhausted"}

    incident = _validated_incident(state)
    previous_actions = state.get("actions_taken", [])
    try:
        model = build_chat_model().with_structured_output(ActionDecision)
        decision = ActionDecision.model_validate(
            model.invoke(
                build_action_prompt(
                    incident=incident,
                    hypotheses=hypotheses,
                    evidence=state.get("evidence", []),
                    actions_taken=previous_actions,
                    remaining_action_budget=budget,
                )
            )
        )
        if decision.action is None:
            return {"status": "selecting_action", "next_action": None, "termination_reason": decision.finish_reason}
        validate_action(
            decision.action,
            known_hypothesis_ids={hypothesis.hypothesis_id for hypothesis in hypotheses},
            previous_actions=previous_actions,
        )
    except Exception as error:
        return {
            "status": "selecting_action",
            "next_action": None,
            "termination_reason": "action_selection_failed",
            "errors": [f"Action selection failed ({type(error).__name__})."],
        }
    return {"status": "selecting_action", "next_action": decision.action}


def execute_action(state: InvestigationState) -> dict:
    """Run one already-validated read-only Phase 2 action and preserve provenance."""
    action = state.get("next_action")
    if action is None:
        return {"status": "executing_action", "errors": ["No action was selected for execution."]}
    action = InvestigationAction.model_validate(action)
    hypotheses = state.get("hypotheses", [])
    previous_actions = state.get("actions_taken", [])
    try:
        validate_action(
            action,
            known_hypothesis_ids={hypothesis.hypothesis_id for hypothesis in hypotheses},
            previous_actions=previous_actions,
        )
        result = _run_action(Path(_validated_incident(state).scenario_dir), action)
        evidence_id = _next_evidence_id(state.get("evidence", []))
        item = build_evidence_item(
            evidence_id=evidence_id,
            evidence_type=_evidence_type_for_tool(action.tool_name),
            source_tool=action.tool_name,
            tool_input=action.tool_input,
            summary=f"Executed targeted action {action.action_id}: {action.purpose}",
            tool_result=result,
        )
        tool_call = build_tool_call_record(
            tool_name=action.tool_name, tool_input=action.tool_input, evidence_id=evidence_id
        )
        return {
            "status": "executing_action",
            "evidence": [item],
            "tools_used": [tool_call],
            "actions_taken": [action],
            "next_action": None,
            "remaining_action_budget": max(state.get("remaining_action_budget", DEFAULT_ACTION_BUDGET) - 1, 0),
        }
    except Exception as error:
        message = f"Action {action.action_id} failed ({type(error).__name__})."
        return {
            "status": "executing_action",
            "tools_used": [build_tool_call_record(tool_name=action.tool_name, tool_input=action.tool_input, error=message)],
            "actions_taken": [action],
            "next_action": None,
            "remaining_action_budget": max(state.get("remaining_action_budget", DEFAULT_ACTION_BUDGET) - 1, 0),
            "errors": [message],
        }


def evaluate_hypotheses(state: InvestigationState) -> dict:
    """Update all alternatives using only gathered evidence and recorded errors."""
    hypotheses = state.get("hypotheses", [])
    if not hypotheses:
        return {"status": "evaluating_hypotheses", "termination_reason": "no_hypotheses"}
    incident = _validated_incident(state)
    evidence = state.get("evidence", [])
    try:
        model = build_chat_model().with_structured_output(HypothesisEvaluation)
        evaluation = HypothesisEvaluation.model_validate(
            model.invoke(
                build_evaluation_prompt(
                    incident=incident,
                    hypotheses=hypotheses,
                    evidence=evidence,
                    errors=state.get("errors", []),
                    remaining_action_budget=state.get("remaining_action_budget", DEFAULT_ACTION_BUDGET),
                )
            )
        )
        _validate_evaluation(evaluation, hypotheses, {item.evidence_id for item in evidence})
    except Exception as error:
        return {
            "status": "evaluating_hypotheses",
            "termination_reason": "hypothesis_evaluation_failed",
            "errors": [f"Hypothesis evaluation failed ({type(error).__name__})."],
        }
    return {
        "status": "evaluating_hypotheses",
        "hypotheses": evaluation.hypotheses,
        "last_evaluation": evaluation,
        "termination_reason": (
            None
            if evaluation.needs_more_evidence and state.get("remaining_action_budget", DEFAULT_ACTION_BUDGET) > 0
            else "action_budget_exhausted" if evaluation.needs_more_evidence else "hypotheses_evaluated"
        ),
    }


def route_after_action_selection(state: InvestigationState) -> str:
    return "execute_action" if state.get("next_action") is not None else "generate_final_report"


def route_after_evaluation(state: InvestigationState) -> str:
    evaluation = state.get("last_evaluation")
    if evaluation is not None and evaluation.needs_more_evidence and state.get("remaining_action_budget", 0) > 0:
        return "select_next_action"
    return "generate_final_report"


def generate_hypothesis_report(state: InvestigationState) -> dict:
    """Render a minimal Phase 3 report from the best evidence-backed hypothesis."""
    incident = _validated_incident(state)
    evidence_ids = {item.evidence_id for item in state.get("evidence", [])}
    supported = [hypothesis for hypothesis in state.get("hypotheses", []) if hypothesis.status == "supported"]
    analysis = None
    if supported:
        best = max(supported, key=lambda hypothesis: hypothesis.confidence)
        analysis = AnalysisResult(
            likely_cause=EvidenceBackedClaim(
                statement=best.statement, evidence_ids=best.supporting_evidence_ids
            ),
            limitations=[
                "Likely cause is the highest-confidence supported hypothesis from the bounded investigation."
            ],
        )
    if analysis is None and state.get("hypotheses"):
        analysis = AnalysisResult(
            limitations=[
                "No hypothesis was sufficiently supported; the investigation remains unresolved.",
                "Competing hypotheses are retained in the investigation trace.",
            ]
        )
    report, validation_errors = build_final_report(
        incident=incident,
        analysis=analysis,
        available_evidence_ids=evidence_ids,
        prior_errors=state.get("errors", []),
    )
    report = attach_investigation_trace(
        report,
        evidence=state.get("evidence", []),
        hypotheses=state.get("hypotheses", []),
        actions_taken=state.get("actions_taken", []),
        termination_reason=state.get("termination_reason"),
    )
    return {"status": "reported", "analysis": analysis, "final_report": report, "errors": validation_errors}


def _run_action(scenario_dir: Path, action: InvestigationAction) -> dict[str, object]:
    tools = {
        "get_pipeline_status": get_pipeline_status,
        "inspect_pipeline_metadata": inspect_pipeline_metadata,
        "search_logs": search_logs,
        "profile_dataset": profile_dataset,
        "compare_distributions": compare_distributions,
    }
    return tools[action.tool_name](scenario_dir, **action.tool_input)


def _evidence_type_for_tool(tool_name: str) -> str:
    return {
        "get_pipeline_status": "PIPELINE_STATUS",
        "inspect_pipeline_metadata": "CONFIGURATION",
        "search_logs": "LOG",
        "profile_dataset": "DATA_QUALITY_METRIC",
        "compare_distributions": "STATISTICAL_ANOMALY",
    }[tool_name]


def _next_evidence_id(evidence: list[object]) -> str:
    indexes = [int(item.evidence_id[1:]) for item in evidence if item.evidence_id.startswith("E") and item.evidence_id[1:].isdigit()]
    return f"E{max(indexes, default=0) + 1:02d}"


def _validate_hypothesis_citations(hypotheses: list[object], evidence_ids: set[str]) -> None:
    for hypothesis in hypotheses:
        citations = set(hypothesis.supporting_evidence_ids) | set(hypothesis.contradicting_evidence_ids)
        unknown = citations - evidence_ids
        if unknown:
            raise ValueError(f"Hypothesis cites unknown evidence IDs: {', '.join(sorted(unknown))}.")


def _validate_evaluation(
    evaluation: HypothesisEvaluation, hypotheses: list[object], evidence_ids: set[str]
) -> None:
    old_ids = {hypothesis.hypothesis_id for hypothesis in hypotheses}
    new_ids = {hypothesis.hypothesis_id for hypothesis in evaluation.hypotheses}
    if new_ids != old_ids:
        raise ValueError("Evaluation must update every existing hypothesis exactly once.")
    _validate_hypothesis_citations(evaluation.hypotheses, evidence_ids)
    unknown = set(evaluation.evidence_ids) - evidence_ids
    if unknown:
        raise ValueError(f"Evaluation cites unknown evidence IDs: {', '.join(sorted(unknown))}.")
