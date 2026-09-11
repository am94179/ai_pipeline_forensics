"""Bounded LangGraph routing for the hypothesis investigation loop."""

from langgraph.graph import END, START, StateGraph

from investigator.agent.hypothesis_nodes import (
    evaluate_hypotheses,
    execute_action,
    generate_hypotheses,
    generate_hypothesis_report,
    route_after_action_selection,
    route_after_evaluation,
    select_next_action,
)
from investigator.agent.nodes import gather_initial_evidence, initialize_incident
from investigator.agent.state import InvestigationState


def build_hypothesis_graph():
    """Compile the small bounded investigation graph with at most three additional actions."""
    workflow = StateGraph(InvestigationState)
    workflow.add_node("initialize_incident", initialize_incident)
    workflow.add_node("gather_initial_evidence", gather_initial_evidence)
    workflow.add_node("generate_hypotheses", generate_hypotheses)
    workflow.add_node("select_next_action", select_next_action)
    workflow.add_node("execute_action", execute_action)
    workflow.add_node("evaluate_hypotheses", evaluate_hypotheses)
    workflow.add_node("generate_final_report", generate_hypothesis_report)

    workflow.add_edge(START, "initialize_incident")
    workflow.add_edge("initialize_incident", "gather_initial_evidence")
    workflow.add_edge("gather_initial_evidence", "generate_hypotheses")
    workflow.add_edge("generate_hypotheses", "select_next_action")
    workflow.add_conditional_edges(
        "select_next_action",
        route_after_action_selection,
        {"execute_action": "execute_action", "generate_final_report": "generate_final_report"},
    )
    workflow.add_edge("execute_action", "evaluate_hypotheses")
    workflow.add_conditional_edges(
        "evaluate_hypotheses",
        route_after_evaluation,
        {"select_next_action": "select_next_action", "generate_final_report": "generate_final_report"},
    )
    workflow.add_edge("generate_final_report", END)
    return workflow.compile()
