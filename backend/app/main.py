import onnxruntime as ort
ort.preload_dlls() # CRITICAL: DO NOT REMOVE

import asyncio
from qdrant_client import AsyncQdrantClient
from fastembed import TextEmbedding, SparseTextEmbedding

from app.agent.llm.router import build_chat_model
from app.agent.config.settings import load_config
from app.agent.tools.tool_registry import build_legal_tools
from app.rag.retrieval.retriever_main import retrieve
from app.rag.retrieval.query_llm.data_models import QueryResponse, EnrichedQuery
from app.db.session import SessionLocal_corpus, SessionLocal_main
from app.common.config import settings



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
    
    tools = build_legal_tools(SessionLocal_corpus, client_q)
    
    llm_rag = build_chat_model(config=cfg.llm, route="rag", schema=QueryResponse)
    llm_agent = build_chat_model(config=cfg.llm, route="agent", tools=tools)
    
    # user query by input 
    query = input("\nYou: ")
    
    rag_result = await retrieve(
        query=query,
        client=client_q,
        dense_model=dense_model,
        sparse_model=sparse_model,
        llm_runnable=llm_rag
    )
    
    print(rag_result)
    
    
    
if __name__ == "__main__":
    asyncio.run(main())
    
    
    
"""
docker startup commands in sequence:

docker compose -f backend/docker-compose.yaml --env-file .env up -d postgres qdrant


"""


# a thief snatched my purse and ran away what should i do next ??