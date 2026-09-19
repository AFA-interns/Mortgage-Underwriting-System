from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.document_ingestion.agent import document_ingestion_node
from app.graph.nodes.credit import credit_node
from app.graph.nodes.property_valuation import property_valuation_node
from app.graph.nodes.compliance import compliance_node
from app.graph.nodes.decision import decision_node
from app.graph.nodes.doc_ingestion_to_analysis import doc_ingestion_to_analysis_node
from app.graph.state import UnderwritingState


def _route_after_decision(state: UnderwritingState) -> str:
    decision = state.get("decision", {})
    decision_type = decision.get("decision", "SUSPEND")
    if decision_type == "SUSPEND":
        return "human_review"
    return "report"


def _human_review_node(state: UnderwritingState) -> dict[str, Any]:
    return {"human_review_required": True}


def _report_node(state: UnderwritingState) -> dict[str, Any]:
    return {}


def build_underwriting_graph() -> StateGraph:
    graph = StateGraph(UnderwritingState)

    # Agent nodes
    graph.add_node("document_ingestion", document_ingestion_node)
    graph.add_node("doc_ingestion_to_analysis", doc_ingestion_to_analysis_node)
    graph.add_node("credit_analysis", credit_node)
    graph.add_node("property_valuation", property_valuation_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("decision", decision_node)

    # Routing nodes
    graph.add_node("human_review", _human_review_node)
    graph.add_node("report", _report_node)

    # Entry point
    graph.set_entry_point("document_ingestion")

    # Document Ingestion -> Transform -> Credit + Property + Compliance (parallel)
    graph.add_edge("document_ingestion", "doc_ingestion_to_analysis")
    graph.add_edge("doc_ingestion_to_analysis", "credit_analysis")
    graph.add_edge("doc_ingestion_to_analysis", "property_valuation")
    graph.add_edge("doc_ingestion_to_analysis", "compliance")

    # All three converge to Decision
    graph.add_edge("credit_analysis", "decision")
    graph.add_edge("property_valuation", "decision")
    graph.add_edge("compliance", "decision")

    # Decision routes to human_review or report
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
