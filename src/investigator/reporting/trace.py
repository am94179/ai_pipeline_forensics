"""Attach the bounded investigation trace to a final report."""

from __future__ import annotations

from collections.abc import Sequence

from investigator.agent.hypotheses import Hypothesis, InvestigationAction
from investigator.agent.state import EvidenceItem, FinalReport


def attach_investigation_trace(
    report: FinalReport,
    *,
    evidence: Sequence[EvidenceItem],
    hypotheses: Sequence[Hypothesis],
    actions_taken: Sequence[InvestigationAction],
    termination_reason: str | None,
) -> FinalReport:
    """Return a report that separates deterministic records from LLM inferences."""
    return report.model_copy(
        update={
            "limitations": [
                *report.limitations,
                "Hypothesis confidence expresses an evidence-constrained LLM judgment, not certainty.",
            ],
            "deterministic_evidence": list(evidence),
            "hypotheses": list(hypotheses),
            "actions_taken": list(actions_taken),
            "termination_reason": termination_reason,
        }
    )
