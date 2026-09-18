from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.graph.state import AgentState
from app.graph.nodes.workflow_nodes import (
    intake_node,
    location_node,
    comps_node,
    api_valuation_node,
    reconcile_node,
    explanation_node
)

def build_graph():
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("location", location_node)
    workflow.add_node("comps", comps_node)
    workflow.add_node("api_valuation", api_valuation_node)
    workflow.add_node("reconcile", reconcile_node)
    workflow.add_node("explanation", explanation_node)
    
    # Define edges
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "location")
    workflow.add_edge("location", "comps")
    workflow.add_edge("comps", "api_valuation")
    workflow.add_edge("api_valuation", "reconcile")
    workflow.add_edge("reconcile", "explanation")
    workflow.add_edge("explanation", END)
    
    # Add checkpointer for human-in-the-loop
    memory = MemorySaver()
    
    # Compile graph with interruption before explanation if human review is needed.
    # In a real app, we might route conditionally. For simplicity, we interrupt before explanation.
    def should_interrupt(state: AgentState):
        return state.get("human_review_required", False)
        
    app = workflow.compile(
        checkpointer=memory,
        interrupt_before=["explanation"]
    )
    
    return app

# Singleton graph instance
valuation_graph = build_graph()
