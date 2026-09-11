"""LangGraph workflow definition for the mortgage underwriting pipeline."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.graph.nodes.decision import decision_node
from app.graph.state import UnderwritingState


def _route_after_decision(state: UnderwritingState) -> str:
    """Route based on decision outcome."""
    decision = state.get("decision", {})
    decision_type = decision.get("decision", "SUSPEND")
    if decision_type == "SUSPEND":
        return "human_review"
    return "report"


def _human_review_node(state: UnderwritingState) -> dict[str, Any]:
    """Placeholder for human review integration — marks for human attention."""
    return {
        "human_review_required": True,
    }


def _report_node(state: UnderwritingState) -> dict[str, Any]:
    """Placeholder for final report delivery."""
    return {}


def build_underwriting_graph() -> StateGraph:
    """Build the LangGraph workflow for mortgage underwriting."""
    graph = StateGraph(UnderwritingState)

    graph.add_node("decision", decision_node)
    graph.add_node("human_review", _human_review_node)
    graph.add_node("report", _report_node)

    graph.set_entry_point("decision")

    graph.add_conditional_edges(
        "decision",
        _route_after_decision,
        {
            "human_review": "human_review",
            "report": "report",
        },
    )

    graph.add_edge("human_review", "report")
    graph.add_edge("report", END)

    return graph
