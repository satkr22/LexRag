import sys
import asyncio
import time

import onnxruntime as ort
ort.preload_dlls() # CRITICAL: DO NOT REMOVE

from qdrant_client import QdrantClient, models

from backend.app.rag.retrieval.query_llm.query import generate_response_gemini, generate_response_qwen
from backend.app.rag.retrieval.query_llm.data_models import QueryResponse, EnrichedQuery



COLLECTION_NAME = "legal_docs"
DENSE_MODEL = "BAAI/bge-large-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
DB_PATH = "./qdrant_db2"
TOP_K = 10

# embedding models warmup
from fastembed import TextEmbedding, SparseTextEmbedding
print("models warmup...")
dense_model = TextEmbedding(model_name=DENSE_MODEL)      # triggers load
sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL) # triggers load
print("models warmup done.")


def build_client() -> QdrantClient:
    return QdrantClient(
        path=DB_PATH,
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider"],
    )


def hybrid_search_expanded(
    client: QdrantClient, 
    query_text: EnrichedQuery, 
    category_ids: list,
    limit: int = 10
):
    """Executes a hybrid search filtered by category IDs using Reciprocal Rank Fusion."""
    t0 = time.perf_counter()
    
    # 1. Define the payload filter
    category_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="category_id", 
                match=models.MatchAny(any=category_ids) 
            )
        ]
    )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=models.Document(text=query_text.dense_query, model=DENSE_MODEL),
                using="", # this is blank because i have first created dense vector without its label
                limit=limit,
                filter=category_filter, # filter to Dense search
            ),
            models.Prefetch(
                query=models.Document(text=query_text.bm25_keywords, model=SPARSE_MODEL),
                using="bm25",
                limit=limit,
                filter=category_filter, # filter to BM25 search
            ),
        ],
        # Combine the results of both prefetch queries 
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True
    )
    
    return results.points, time.perf_counter() - t0


def format_hit(rank: int, point) -> str:
    p = point.payload or {}
    text = (p.get("text") or "").replace("\n", " ").strip()
    snippet = text
    return (
        f"  [{rank}] score={point.score:.4f}  "
        f"section={p.get('section_id', '?')}  "
        f"chunk={p.get('chunk_id', '?')}  "
        f"tokens={p.get('token_count', '?')}\n"
        f"      {snippet}"
    )


def show_expanded(client: QdrantClient, query: EnrichedQuery, category_list: list, top_k: int = TOP_K):
    print("\n\n")
    print(f"\n=== EnrichedQuery:\n=== Dense_query: {query.dense_query}\n=== Sparse_query: {query.bm25_keywords}")
    print(f"\n=== Category_list: {category_list}")
    
    hits, elapsed = hybrid_search_expanded(client, query, category_list, top_k)
    
    print(f"  ({len(hits)} hits in {elapsed*1000:.1f} ms)")
    for rank, point in enumerate(hits, 1):
        print(format_hit(rank, point))
    
    print("\n\n\n")
    return hits

def print_labels(client:QdrantClient):
    if not client.collection_exists(COLLECTION_NAME):
        print(f"ERROR: collection '{COLLECTION_NAME}' not found. Run embedder_gpu.py first.")
        sys.exit(1)
        
    info = client.get_collection(COLLECTION_NAME)
    v = info.config.params.vectors
    print(f"Collection: {COLLECTION_NAME}")
    print(f"dims: {v.size}  distance={v.distance}") # type: ignore
    print(f"points: {info.points_count}")
    print(f"Dense model: {DENSE_MODEL}")
    print(f"Sparse model: {SPARSE_MODEL}")


async def main(user_query: str):
    
    client = build_client()
    
    print_labels(client)
    try: 
        # result = generate_response_gemini(user_query)
        result:QueryResponse = await generate_response_qwen(user_query)
        show_expanded(client, result.enriched_query, result.category_ids, 5)
    except Exception as e:
            print(f"Some error occured: {e}")
    client.close()
        
if __name__ == "__main__":
    
    user_query: str = "how to file an rti"
    asyncio.run(main(user_query))

    
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
