"""Prompts for the bounded hypothesis workflow."""

from __future__ import annotations

import json
from collections.abc import Sequence

from investigator.agent.hypotheses import Hypothesis, InvestigationAction
from investigator.agent.state import EvidenceItem, IncidentInput


def build_hypothesis_prompt(
    *, incident: IncidentInput, evidence: Sequence[EvidenceItem], errors: Sequence[str]
) -> str:
    payload = _base_payload(incident, evidence, errors)
    instructions = """Propose two to four distinct, plausible root-cause hypotheses.
Use supplied evidence only. Each hypothesis must have a stable ID, a concise statement,
an open status, confidence from 0 to 1, and rationale. Cite only existing evidence IDs
when evidence supports or contradicts it; an open hypothesis may have no citations.
Do not choose a final cause, read files, use tools, or mention ground truth.
Return the requested structured schema."""
    return f"{instructions}\nInvestigation data:\n{json.dumps(payload, sort_keys=True)}"


def build_action_prompt(
    *,
    incident: IncidentInput,
    hypotheses: Sequence[Hypothesis],
    evidence: Sequence[EvidenceItem],
    actions_taken: Sequence[InvestigationAction],
    remaining_action_budget: int,
) -> str:
    payload = _base_payload(incident, evidence, [])
    payload.update(
        {
            "hypotheses": [hypothesis.model_dump(mode="json") for hypothesis in hypotheses],
            "actions_taken": [action.model_dump(mode="json") for action in actions_taken],
            "remaining_action_budget": remaining_action_budget,
            "allowed_tools": [
                "get_pipeline_status",
                "inspect_pipeline_metadata",
                "search_logs",
                "profile_dataset",
                "compare_distributions",
            ],
        }
    )
    instructions = """Choose at most one targeted, read-only action that resolves a recorded
uncertainty. Use only the listed tools and public registered dataset names. Do not repeat
an action already taken. If no action would materially improve the investigation, return
a finish reason instead. Never request paths, arbitrary code, shell commands, or ground
truth. Return the requested structured schema."""
    return f"{instructions}\nInvestigation data:\n{json.dumps(payload, sort_keys=True)}"


def build_evaluation_prompt(
    *,
    incident: IncidentInput,
    hypotheses: Sequence[Hypothesis],
    evidence: Sequence[EvidenceItem],
    errors: Sequence[str],
    remaining_action_budget: int,
) -> str:
    payload = _base_payload(incident, evidence, errors)
    payload.update(
        {
            "hypotheses": [hypothesis.model_dump(mode="json") for hypothesis in hypotheses],
            "remaining_action_budget": remaining_action_budget,
        }
    )
    instructions = """Update every supplied hypothesis without discarding alternatives.
Use only existing evidence IDs for supporting, contradicting, and evaluation citations.
Mark a hypothesis supported only with supporting evidence and rejected only with
contradicting evidence. Set needs_more_evidence only when a safe additional action could
materially help and budget remains. Do not read files, use tools, or mention ground truth.
Return the requested structured schema."""
    return f"{instructions}\nInvestigation data:\n{json.dumps(payload, sort_keys=True)}"


def _base_payload(
    incident: IncidentInput, evidence: Sequence[EvidenceItem], errors: Sequence[str]
) -> dict[str, object]:
    return {
        "incident": {
            "incident_id": incident.incident_id,
            "description": incident.description,
            "reported_at": incident.reported_at,
        },
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "errors": list(errors),
    }
