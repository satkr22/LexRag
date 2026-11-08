import onnxruntime as ort
ort.preload_dlls() # CRITICAL: DO NOT REMOVE

import json
import asyncio
from pathlib import Path
from qdrant_client import AsyncQdrantClient
from fastembed import TextEmbedding, SparseTextEmbedding

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage

from app.common.config import settings
from app.db.session import SessionLocal_corpus, SessionLocal_main

from app.agent.llm.router import build_chat_model
from app.agent.config.settings import load_config
from app.agent.tools.tool_registry import build_legal_tools
from app.agent.graph.graph import create_graph

from app.rag.retrieval.retriever_main import retrieve
from app.rag.retrieval.query_llm.data_models import QueryResponse

from app.stream import streaming




def _build_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=settings.QDRANT_URL, 
        timeout=120
    )
    
def _warmup_embedding_models():
    dense_model = TextEmbedding(
        model_name=settings.DENSE_MODEL_NAME,
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
    )
    sparse_model = SparseTextEmbedding(
        model_name=settings.SPARSE_MODEL_NAME, 
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
    )
    dummy_text = "warmup"
    list(dense_model.embed([dummy_text]))
    list(sparse_model.embed([dummy_text]))
    
    return dense_model, sparse_model


async def main():
    
    client_q = _build_qdrant_client()
    
    dense_model, sparse_model = _warmup_embedding_models()
    
    cfg = load_config()
    
    tools = await build_legal_tools(
        session_factory=SessionLocal_corpus, 
        client=client_q,
        dense_model=dense_model,
        sparse_model=sparse_model
    )
    
    llm_rag = build_chat_model(config=cfg.llm, route="rag", schema=QueryResponse)
    llm_agent = build_chat_model(config=cfg.llm, route="agent", tools=tools)
    
    agent_system_prompt = Path(cfg.agent.system_prompt).resolve().read_text()
            
    graph = create_graph(
        executor_model=llm_agent,
        structured_tools=tools,
    )
    
    config: RunnableConfig = {
        "configurable": {"thread_id": "__lexrag__"},
        "recursion_limit": 200,
    }
    
    while True:
        try:
            # user query by input 
            query = input("\nYou: ")
            if query == "/exit":
                break
            
            rag_result = await retrieve(
                query=query,
                client=client_q,
                dense_model=dense_model,
                sparse_model=sparse_model,
                llm_runnable=llm_rag
            )
            
            if rag_result.get("retriver_failed"):
                seed_message = f"User Query: {query}"
                
            else:
                seed_message: str = f"""
                User Query: {query}\n\n
                Below is the initial result obtained from RAG Hybrid retrieval for the above given user query:\n\n
                {json.dumps(rag_result, indent=2)}\n\n
                """
            
            payload = {
                "executor_messages": [
                    SystemMessage(agent_system_prompt),
                    HumanMessage(seed_message),
                ],
                "task": query,
                "iteration": 0,
            }
            
            token_usage = await streaming(
                graph=graph,
                payload=payload,
                config=config,
            )
            
            if token_usage:
                print("\n\nToken Usage:\n")
                print("Input:", token_usage.get("input_tokens", 0))
                print("Output:", token_usage.get("output_tokens", 0))
                print("Total:", token_usage.get("total_tokens", 0))
                print("Cache read:", token_usage.get("input_token_details", {}).get("cache_read", 0))
                print("New Charged Token Input", token_usage.get("input_tokens", 0) - token_usage.get("input_token_details", {}).get("cache_read", 0))
                print("New Charged Token Output", token_usage.get("output_tokens", 0))

            
        except Exception as e:
            print(f"Error Ocuured : {e}")
            continue

        
    
    
if __name__ == "__main__":
    asyncio.run(main())
    
    
    
"""
docker startup commands in sequence:

docker compose -f backend/docker-compose.yaml --env-file .env up -d postgres qdrant
docker compose -f docker-compose.yaml --env-file ../.env up -d postgres qdrant


"""


# a thief snatched my purse and ran away what should i do next ??