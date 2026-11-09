import json
from pathlib import Path

from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.messages import ToolMessage, AIMessage, SystemMessage, RemoveMessage, HumanMessage
from langchain_core.tools import StructuredTool

from app.agent.graph.state import AgentState
from app.agent.prompts import *



def create_agent_node(model: Runnable):
    
    async def agent_node(state: AgentState, config: RunnableConfig):
        
        messages_to_send = list(state["executor_messages"])

        response: AIMessage = await model.with_config(config).ainvoke(messages_to_send)
        
        new_tokens_count = 0
        token_usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            token_usage = response.usage_metadata
            new_tokens_count = response.usage_metadata.get("total_tokens", 0)
        
        return {
            "executor_messages": [response],
            "iteration": state["iteration"] + 1,
            "current_context_window": new_tokens_count,
            "token_usage": token_usage,
        }
    return agent_node



def create_compression_node(model: Runnable):

    async def compression_node(state: AgentState, config: RunnableConfig):
        
        messages = state["executor_messages"]
            
        summary_prompt = f"Condense the following conversation into a dense summary. Retain all specific legal facts, user constraints, and Indian statutory references. Messages are:\n\n{messages}"
        
        messages_to_send = [HumanMessage(content=summary_prompt)]
        
        response: AIMessage = await model.with_config(config).ainvoke(messages_to_send)
        
        new_tokens_count = 0
        token_usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            token_usage = response.usage_metadata
            new_tokens_count = response.usage_metadata.get("total_tokens", 0)
        
        delete_messages = [RemoveMessage(id=m.id) for m in messages if m.id]
        
        summary_message = SystemMessage(content=f"Summary of previous conversation: {response.content}")
        
        system_prompt = ""
        p = Path("app/agent/prompts/system.md").resolve()
        if p.exists() and p.is_file():
            system_prompt = p.read_text(encoding="utf-8")
        
        return {
            "executor_messages": delete_messages + [SystemMessage(system_prompt)] + [summary_message],
            "current_context_window": new_tokens_count,
            "is_compressed": True,
            "token_usage": token_usage,
        }
    
    return compression_node
            

def create_tool_node(tools: list[StructuredTool]):
    tool_map = {t.name: t for t in tools}

    async def tool_node(state: AgentState, config: RunnableConfig):
        
        last: AIMessage = state["executor_messages"][-1] # type: ignore
 
        if not getattr(last, "tool_calls", None):
            return {"executor_messages": []}

        tool_messages: list[ToolMessage] = []

        for tc in last.tool_calls:
            name = tc["name"]
            call_id = tc["id"]
            args = tc.get("args", {})

            tool = tool_map.get(name)
            if tool is None:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: unknown tool '{name}'",
                        tool_call_id=call_id,
                        name=name,
                        status="error",
                    )
                )
                continue

            try:
                result = await tool.ainvoke(args, config)
                content = (
                    result
                    if isinstance(result, str)
                    else json.dumps(result, ensure_ascii=False, default=str)
                )
                tool_messages.append(
                    ToolMessage(
                        content=content, 
                        tool_call_id=call_id, 
                        name=name
                    )
                )
            except Exception as e:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing {name}: {e!s}",
                        tool_call_id=call_id,
                        name=name,
                        status="error",
                    )
                )

        return {"executor_messages": tool_messages}

    return tool_node