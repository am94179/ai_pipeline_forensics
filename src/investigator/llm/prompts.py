"""Prompt construction for bounded, evidence-backed LLM analysis."""

from __future__ import annotations

import json
from collections.abc import Sequence

from investigator.agent.state import EvidenceItem, IncidentInput


def build_analysis_prompt(
    *,
    incident: IncidentInput,
    evidence: Sequence[EvidenceItem],
    gathering_errors: Sequence[str],
) -> str:
    """Build an analysis prompt from only the allowed investigation state."""
    payload = {
        "incident": {
            "incident_id": incident.incident_id,
            "description": incident.description,
            "reported_at": incident.reported_at,
        },
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "gathering_errors": list(gathering_errors),
    }
    instructions = """You are analyzing a data-pipeline incident using supplied evidence only.

Separate observations (what the evidence directly shows) from inferences. Every
observation, likely-cause claim, and impact claim must cite one or more existing
evidence IDs. Do not cite IDs that are not present. State limitations when the
evidence is insufficient or contradictory. Do not treat missing evidence as proof
of a cause. Do not request additional tools or actions beyond one recommended next
action. Return output matching the requested structured schema.
"""
    return f"{instructions}\nInvestigation data:\n{json.dumps(payload, sort_keys=True)}"
