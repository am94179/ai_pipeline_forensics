"""Bounded hypothesis-planning contracts and action validation."""

from __future__ import annotations

from investigator.agent.hypotheses import Hypothesis, InvestigationAction
from pydantic import BaseModel, Field, model_validator


class HypothesisSet(BaseModel):
    """The bounded set of alternatives proposed before further investigation."""

    hypotheses: list[Hypothesis] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def hypothesis_ids_must_be_distinct(self) -> "HypothesisSet":
        hypothesis_ids = [hypothesis.hypothesis_id for hypothesis in self.hypotheses]
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ValueError("Hypothesis IDs must be distinct.")
        return self


class ActionDecision(BaseModel):
    """A choice to execute one safe action or to end investigation."""

    action: InvestigationAction | None = None
    finish_reason: str | None = None

    @model_validator(mode="after")
    def must_choose_action_or_finish(self) -> "ActionDecision":
        if (self.action is None) == (self.finish_reason is None):
            raise ValueError("Provide exactly one of action or finish_reason.")
        if self.finish_reason is not None and not self.finish_reason.strip():
            raise ValueError("Finish reason cannot be blank.")
        return self


SAFE_DATASETS = frozenset(
    {
        "baseline_source_orders",
        "incident_source_orders",
        "baseline_transformed_orders",
        "incident_transformed_orders",
        "baseline_warehouse_orders",
        "incident_warehouse_orders",
    }
)


def validate_action(
    action: InvestigationAction,
    *,
    known_hypothesis_ids: set[str],
    previous_actions: list[InvestigationAction],
) -> None:
    """Reject unsupported, duplicate, or unsafe deterministic-tool requests."""
    unknown_hypotheses = set(action.target_hypothesis_ids) - known_hypothesis_ids
    if unknown_hypotheses:
        raise ValueError(
            "Action targets unknown hypothesis IDs: "
            f"{', '.join(sorted(unknown_hypotheses))}."
        )
    if action.action_id in {previous.action_id for previous in previous_actions}:
        raise ValueError(f"Action ID '{action.action_id}' was already used.")
    if any(_fingerprint(action) == _fingerprint(previous) for previous in previous_actions):
        raise ValueError("Action duplicates a previous tool request.")
    _validate_tool_input(action.tool_name, action.tool_input)


def _fingerprint(action: InvestigationAction) -> tuple[str, tuple[tuple[str, str], ...]]:
    return action.tool_name, tuple(sorted((key, repr(value)) for key, value in action.tool_input.items()))


def _validate_tool_input(tool_name: str, tool_input: dict[str, object]) -> None:
    allowed_inputs = {
        "get_pipeline_status": {"run_date"},
        "inspect_pipeline_metadata": set(),
        "search_logs": {"query", "start_time", "end_time", "level", "component"},
        "profile_dataset": {"dataset", "categorical_columns", "sample_size"},
        "compare_distributions": {"baseline_dataset", "incident_dataset", "categorical_columns"},
    }
    if tool_name not in allowed_inputs:
        raise ValueError(f"Tool '{tool_name}' is not in the investigation action catalog.")
    unknown_inputs = set(tool_input) - allowed_inputs[tool_name]
    if unknown_inputs:
        raise ValueError(
            f"Unsupported input for {tool_name}: {', '.join(sorted(unknown_inputs))}."
        )
    if tool_name == "profile_dataset":
        _require_dataset(tool_input, "dataset")
    elif tool_name == "compare_distributions":
        _require_dataset(tool_input, "baseline_dataset")
        _require_dataset(tool_input, "incident_dataset")


def _require_dataset(tool_input: dict[str, object], field_name: str) -> None:
    if tool_input.get(field_name) not in SAFE_DATASETS:
        raise ValueError(f"{field_name} must name a public registered dataset.")
