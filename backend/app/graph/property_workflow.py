from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.property_state import AgentState

from app.graph.nodes.property import (
    intake_node,
    location_node,
    comps_node,
    api_valuation_node,
    reconcile_node,
    explanation_node,
)


def human_review_router(state: AgentState):
    """
    Decide whether the valuation requires human review.

    If human_review_required is True, pause before explanation.
    Otherwise continue directly to explanation.
    """

    if state.get("human_review_required", False):
        return "human_review"

    return "explanation"


def build_property_graph():

    workflow = StateGraph(AgentState)

    # ---------------------------------------------------
    # Nodes
    # ---------------------------------------------------

    workflow.add_node(
        "intake",
        intake_node
    )

    workflow.add_node(
        "location",
        location_node
    )

    workflow.add_node(
        "comps",
        comps_node
    )

    workflow.add_node(
        "api_valuation",
        api_valuation_node
    )

    workflow.add_node(
        "reconcile",
        reconcile_node
    )

    workflow.add_node(
        "explanation",
        explanation_node
    )

    # ---------------------------------------------------
    # Human review node
    #
    # This node does nothing itself.
    # The API can interrupt before it when required.
    # ---------------------------------------------------

    workflow.add_node(
        "human_review",
        lambda state: state
    )

    # ---------------------------------------------------
    # Main flow
    # ---------------------------------------------------

    workflow.set_entry_point("intake")

    workflow.add_edge(
        "intake",
        "location"
    )

    workflow.add_edge(
        "location",
        "comps"
    )

    workflow.add_edge(
        "comps",
        "api_valuation"
    )

    workflow.add_edge(
        "api_valuation",
        "reconcile"
    )

    # ---------------------------------------------------
    # After reconciliation:
    #
    # human_review_required = True
    #       -> human_review
    #
    # human_review_required = False
    #       -> explanation
    # ---------------------------------------------------

    workflow.add_conditional_edges(
        "reconcile",
        human_review_router,
        {
            "human_review": "human_review",
            "explanation": "explanation",
        },
    )

    # ---------------------------------------------------
    # After human review, continue to explanation
    # ---------------------------------------------------

    workflow.add_edge(
        "human_review",
        "explanation"
    )

    workflow.add_edge(
        "explanation",
        END
    )

    # ---------------------------------------------------
    # Compile
    # ---------------------------------------------------

    memory = MemorySaver()

    app = workflow.compile(
        checkpointer=memory,
        interrupt_before=["human_review"],
    )

    return app


valuation_graph = build_property_graph()