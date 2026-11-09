from typing import Literal

from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph.state import AgentState
from app.agent.graph.nodes import (
    create_agent_node,
    create_tool_node,
    create_compression_node,
)


MAX_ITERATION = 100


def route_executor(
    state: AgentState
) -> Literal["__end__", "tools", "compressor"]:
    
    if state["iteration"] >= MAX_ITERATION:
        return "__end__"
    
    if state["current_context_window"] >= state["compression_threshold"]:
        return "compressor"
    
    msgs = state["executor_messages"]
    last = msgs[-1]
    if isinstance(last, AIMessage):
        if not last.tool_calls:
            return "__end__"
        return "tools"
    else:
        return "__end__"
    

def create_graph(
    executor_model,
    structured_tools: list[StructuredTool],
    checkpointer=None,
):
    
    executor_node = create_agent_node(executor_model)
    tool_node = create_tool_node(structured_tools)
    compression_node = create_compression_node(executor_model)
    
    g = StateGraph(AgentState)
    
    # NODES
    g.add_node("executor", executor_node)
    g.add_node("tools", tool_node)
    g.add_node("compressor", compression_node)
    
    # EDGES 
    g.add_edge(START, "executor")
    
    g.add_conditional_edges(
        "executor",
        route_executor,
        {
            "tools": "tools",
            "compressor": "compressor",
            "__end__": END,
            "__max_iteration_limit__": END,
        }
    )
    
    g.add_edge("tools", "executor")
    g.add_edge("compressor", END)
    
    return g.compile(checkpointer=checkpointer or MemorySaver())
    