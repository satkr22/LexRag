from typing import TypedDict, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    
    executor_messages: Annotated[
        list[BaseMessage],
        add_messages,
    ]
    
    task: str
    
    iteration: int
    
    context_window: int
    compression_threshold: int
    current_context_window: int
    
    is_compressed: bool
    
    token_usage: dict