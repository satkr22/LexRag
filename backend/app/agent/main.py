import onnxruntime as ort
ort.preload_dlls() # CRITICAL: DO NOT REMOVE

import json
import asyncio
from pathlib import Path
from qdrant_client import AsyncQdrantClient
from fastembed import TextEmbedding, SparseTextEmbedding

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.common.config import settings
from app.db.session import SessionLocal_corpus, SessionLocal_users

from app.agent.llm.router import build_chat_model
from app.agent.config.settings import load_config
from app.agent.tools.tool_registry import build_legal_tools
from app.agent.graph.graph import create_graph

from app.rag.retrieval.retriever_main import retrieve
from app.rag.retrieval.query_llm.data_models import QueryResponse

from backend.app.agent.stream import streaming




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


def _print_token_usage(token_usage: dict):
    
    print("\n\nToken Usage:\n")
    print("Input:", token_usage.get("input_tokens", 0))
    print("Output:", token_usage.get("output_tokens", 0))
    print("Total:", token_usage.get("total_tokens", 0))
    
    print("Cache read:", token_usage.get("input_token_details", {}).get("cache_read", 0))
    
    print("Cache read Charge:", token_usage.get("input_token_details", {}).get("cache_read", 0))
    
    print("Input Token Charge:", token_usage.get("input_tokens", 0) - token_usage.get("input_token_details", {}).get("cache_read", 0))
    
    print("Output Token Charge:", token_usage.get("output_tokens", 0))

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
    
    DB_URI = settings.DATABASE_URL_MAIN
    
    evaluation_dict = {}
    
    async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
        
        # create checkpoints tables if they dont exist
        await checkpointer.setup()
        
        graph = create_graph(
            executor_model=llm_agent,
            structured_tools=tools,
            checkpointer=checkpointer
        )
    
        config: RunnableConfig = {
            "configurable": {
                "thread_id": "__lexrag__"
            },
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
                
                # for evaluation dataset
                evaluation_dict["seed_rag_result"] = rag_result
                
                retrieved = False
                if rag_result.get("retriver_failed"):
                    seed_message = f"User Query: {query}"
                else:
                    seed_message: str = f"""
                    User Query: {query}\n\n
                    Below is the initial routing result from RAG Hybrid retrieval:
                    - Requires Retrieval: {rag_result.get("requires_retrieval")}
                    - Initial Results Count: {rag_result.get("count")}
                    
                    Data Payload:
                    {json.dumps(rag_result.get("results"), indent=2)}
                    
                    - Hint: {rag_result.get("hint")}
                    """
                    retrieved = True
                
                print("\nseed:", retrieved, "\n\n\n")
                print(seed_message)
            
                
                # check the current state of this thread from PostgreSQL checkpointer
                current_state = await graph.aget_state(config)
                
                # if there are no messages in the state, it's a new thread
                existing_messages = current_state.values.get("executor_messages", [])
                current_context_window = current_state.values.get("current_context_window", 0)
                token_usage = current_state.values.get("token_usage", {})
                
                is_new_thread = len(existing_messages) == 0
                
                if is_new_thread == False:
                    print("\nGot the old context\n")
                
                messages_to_send = []
                
                if is_new_thread:
                    messages_to_send.append(SystemMessage(agent_system_prompt))
                
                messages_to_send.append(HumanMessage(seed_message))
                
                payload = {
                    "executor_messages": messages_to_send,
                    "task": query,
                    "iteration": 0, # this iteration is per chat
                    "context_window": cfg.llm.providers[cfg.llm.agent.active_provider].context_window,
                    "compression_threshold": cfg.llm.providers[cfg.llm.agent.active_provider].compression_threshold,
                    "current_context_window": current_context_window,
                    "is_compressed": False,
                    "token_usage": token_usage,
                }
                
                dict_retunred = await streaming(
                    graph=graph,
                    payload=payload,
                    config=config,
                    evaluation_dict=evaluation_dict
                )
                
                if dict_retunred["token_usage"]:
                    _print_token_usage(dict_retunred["token_usage"])
                
                if dict_retunred["is_compressed"]:
                    print("Context is compressed. Please ask you question again.")
                    
                if dict_retunred["evaluation_dict"]:
                    eval_dir =  Path("app/agent").resolve() / "evaluation"
                    eval_dir.mkdir(parents=True, exist_ok=True)
                    eval_json = eval_dir / f"eval_{config["configurable"]["thread_id"]}.jsonl" 
                    
                    with eval_json.open("a", encoding="utf-8") as f:
                        f.write(f"{json.dumps(evaluation_dict, ensure_ascii=False, indent= 2)}\n")
                
            except Exception as e:
                print(f"Error Ocuured : {e}")
                continue

            
        
    
if __name__ == "__main__":
    asyncio.run(main())
    
    
    
    

"""
startup commands in sequence:

cd backend
docker compose up -d postgres qdrant
python -m app.main

"""

"""
# alembic

# for initialization:
$ alembic -c alembic-users.ini init alembic_users
then edit env.py and .ini file


# for running migrations:
$ alembic -c alembic-users.ini revision --autogenerate -m "message"


# for applying migration to db
NOTE(CRITICAL): always check auto-generated migrations bfore applying it
$ alembic -c alembic-users.ini upgrade head


# for checking current migration head
$ alembic -c alembic-users.ini current

"""


# docker compose -f docker-compose.yaml --env-file ../.env up -d postgres qdrant





"""
test_queries = [
    # Cross-Category Queries (Tests Router Multi-Labeling)
    "What is the limitation period for filing a suit for a breached commercial contract?",
    "Is electronic evidence, such as a WhatsApp chat, admissible to prove domestic violence?",
    "If a minor inherits immovable property, can their guardian sell it without court permission?",
    "What are the penalties for a company director if a corporate cheque bounces due to insufficient funds?",

    # Dense/Semantic Heavy Queries (Tests Vector Retrieval)
    "Can I back out of a property purchase if the seller hid the fact that the roof was collapsing?",
    "My boss promised me a partnership share but only gave it to me verbally, is that legally binding?",
    "What happens to a person's bank accounts and house if they die without writing a will?",
    "A police officer refused to register my complaint about a stolen phone. What are my options?",

    # Lexical/Keyword Heavy Queries (Tests BM25 Search)
    "What are the grounds for eviction under the Transfer of Property Act 1882?",
    "What is the penalty for cyber terrorism under Section 66F of the Information Technology Act?",
    "Define 'Data Fiduciary' and 'Data Principal' under the Digital Personal Data Protection Act 2023.",
    "What constitutes 'organized crime' under the Bharatiya Nyaya Sanhita 2023?",

    # Out-of-Distribution & Edge Cases (Tests System Boundaries)
    "What is the procedure for registering a trademark for my new clothing brand?",
    "What are the labor laws regarding maximum working hours in a factory?",
    "How much security deposit can a landlord legally demand in Delhi?",

    # Procedural vs. Substantive Exceptions (Tests Chunking & Context)
    "Is an oral agreement to sell real estate valid, or does it strictly require registration?",
    "Can a consumer court reject a complaint if the product was bought for commercial resale?",
    "Under what exact conditions can the police arrest someone without a warrant under the BNSS?"
]

"""
