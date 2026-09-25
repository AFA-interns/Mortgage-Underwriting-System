from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.graph.property_state import AgentState
from app.graph.nodes.property import (
    intake_node,
    location_node,
    api_valuation_node,
    reconcile_node,
    explanation_node,
)


def build_property_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("location", location_node)
    workflow.add_node("api_valuation", api_valuation_node)
    workflow.add_node("reconcile", reconcile_node)
    workflow.add_node("explanation", explanation_node)

    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "location")
    workflow.add_edge("location", "api_valuation")
    workflow.add_edge("api_valuation", "reconcile")
    workflow.add_edge("reconcile", "explanation")
    workflow.add_edge("explanation", END)

    memory = MemorySaver()

    app = workflow.compile(
        checkpointer=memory,
        interrupt_before=["explanation"],
    )

    return app


valuation_graph = build_property_graph()
