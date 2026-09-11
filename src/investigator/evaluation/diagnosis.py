"""Small deterministic classification of evaluation diagnosis wording."""

from __future__ import annotations

from .models import EvaluationCase


def diagnosis_status(case: EvaluationCase, cause: str) -> str:
    """Classify a reported cause without semantic-model judging."""
    if not cause.strip():
        return "no_diagnosis"
    if any(keyword.lower() in cause for keyword in case.accepted_keywords):
        return "correct"
    if any(phrase.lower() in cause for phrase in case.allowed_ambiguity):
        return "ambiguous"
    return "incorrect"
