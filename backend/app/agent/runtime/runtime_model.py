from dataclasses import dataclass
from langchain_core.runnables import Runnable
from qdrant_client import AsyncQdrantClient
from fastembed import TextEmbedding, SparseTextEmbedding
from langgraph.graph.state import CompiledStateGraph
from app.agent.config.settings import AppConfig

@dataclass
class AgentRuntime:
    
    cfg: AppConfig

    qdrant: AsyncQdrantClient

    dense_model: TextEmbedding
    sparse_model: SparseTextEmbedding

    graph: CompiledStateGraph

    llm_rag: Runnable
    llm_agent: Runnable
    system_prompt: str