import onnxruntime as ort
ort.preload_dlls() # CRITICAL: DO NOT REMOVE


from app.agent.llm.router import build_chat_model
from app.agent.config.settings import load_config
from app.agent.tools.tool_registry import build_legal_tools
from app.db.session import SessionLocal_corpus, SessionLocal_main
from app.common.config import settings


from qdrant_client import AsyncQdrantClient



def _build_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=settings.QDRANT_URL,
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider", "CPUExecutionProvider"] if settings.QDRANT_INFERENCE_CUDA else None,
    )


def main():
    
    client_q = _build_qdrant_client()
    
    cfg = load_config()
    
    tools = build_legal_tools(SessionLocal_corpus, client_q)
    
    
    
    
    