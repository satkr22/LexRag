import json

from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.messages import ToolMessage, AIMessage
from langchain_core.tools import StructuredTool

from app.agent.graph.state import AgentState



def create_agent_node(model: Runnable):
    
    async def agent_node(state: AgentState, config: RunnableConfig):
        
        messages_to_send = list(state["executor_messages"])

        response: AIMessage = await model.with_config(config).ainvoke(messages_to_send)
        
        return {
            "executor_messages": [response],
            "iteration": state["iteration"] + 1,
        }
    return agent_node
        

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