import sys
import time
from pathlib import Path
from typing import Optional

import onnxruntime as ort
ort.preload_dlls()

from qdrant_client import QdrantClient, models

COLLECTION_NAME = "legal_docs"
DENSE_MODEL_NAME = "BAAI/bge-large-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"
DB_PATH         = "./qdrant_db2"
TOP_K           = 10

def build_client() -> QdrantClient:
    return QdrantClient(
        path=DB_PATH,
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider"],
    )


def hybrid_search(client: QdrantClient, query_text: str, limit: int = 10):
    """Executes a hybrid search using both BM25 and Dense embeddings via Reciprocal Rank Fusion."""
    t0 = time.perf_counter()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=models.Document(text=query_text, model=DENSE_MODEL_NAME),
                # using="dense",
                using="", # since i have migrated the bm25 to dense vectors which are unnamed vectors
                limit=limit * 2, 
            ),
            models.Prefetch(
                query=models.Document(text=query_text, model=SPARSE_MODEL_NAME),
                using="bm25",
                limit=limit * 2,
            ),
        ],
        
        # Combine the results of both prefetch queries 
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True
    )
    return results.points, time.perf_counter() - t0


def hybrid_search_expanded(client: QdrantClient, query_text: dict, limit: int = 10):
    """Executes a hybrid search using both BM25 and Dense embeddings via Reciprocal Rank Fusion."""
    t0 = time.perf_counter()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=models.Document(text=query_text["dense_query"], model="BAAI/bge-large-en-v1.5"),
                using="", 
                limit=20,
            ),
            models.Prefetch(
                query=models.Document(text=query_text["bm25_keywords"], model="Qdrant/bm25"),
                using="bm25",
                limit=20,
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
    # snippet = text[:220] + ("..." if len(text) > 220 else "")
    return (
        f"  [{rank}] score={point.score:.4f}  "
        f"section={p.get('section_id', '?')}  "
        f"chunk={p.get('chunk_id', '?')}  "
        f"tokens={p.get('token_count', '?')}\n"
        f"      {snippet}"
    )

def show(client: QdrantClient, query: str, top_k: int = TOP_K):
    print(f"\n=== Query: {query!r}")
    hits, elapsed = hybrid_search(client, query, top_k)
    print(f"  ({len(hits)} hits in {elapsed*1000:.1f} ms)")
    for rank, point in enumerate(hits, 1):
        print(format_hit(rank, point))
    return hits

def show_expanded(client: QdrantClient, query: dict, top_k: int = TOP_K):
    print(f"\n=== Query: {query!r}")
    hits, elapsed = hybrid_search_expanded(client, query, top_k)
    print(f"  ({len(hits)} hits in {elapsed*1000:.1f} ms)")
    for rank, point in enumerate(hits, 1):
        print(format_hit(rank, point))
    return hits

QUERIES = [
    "What is the punishment for dowry harassment?",
    "How is income tax calculated on capital gains?",
    "What are the grounds for divorce under Hindu marriage law?",
    "What are the duties of a company director?",
    "How does the RTI Act define a public authority?",
    "What is the limitation period for filing a civil suit?",
    "Can a consumer file a complaint against a service provider?",
    "What are the provisions for anticipatory bail?",
]

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

QUERIES_EXPANDED = {

    "q1": {
        "dense_query": "What is the punishment for cruelty by husband or relatives of husband for demand of dowry under Bharatiya Nyaya Sanhita?",
        "bm25_keywords": "cruelty husband relatives demand dowry punishment section Bharatiya Nyaya Sanhita BNS"
    },
    
    "q2": {
        "dense_query": "What are the statutory provisions for direction for grant of bail to person apprehending arrest under Bharatiya Nagarik Suraksha Sanhita?",
        "bm25_keywords": "direction grant bail person apprehending arrest section Bharatiya Nagarik Suraksha Sanhita BNSS anticipatory bail"
    },
    
    "q3": {
        "dense_query": "How is income tax computed on capital gains under the Income-tax Act, 1961?",
        "bm25_keywords": "capital gains short-term long-term tax computation rates Income tax Act 1961 section 45"
    },

    "q4": {
        "dense_query": "What are the statutory grounds for dissolution of marriage by a decree of divorce under the Hindu Marriage Act, 1955?",
        "bm25_keywords": "dissolution of marriage decree of divorce statutory grounds Section 13 Hindu Marriage Act 1955"
    },

    "q5": {
        "dense_query": "What are the statutory duties of directors under the Companies Act, 2013?",
        "bm25_keywords": "duties of directors statutory liabilities standard of care Section 166 Companies Act 2013"
    },

    "q6": {
        "dense_query": "How is public authority defined under the Right to Information Act, 2005?",
        "bm25_keywords": "public authority definition clause Section 2 h Right to Information Act 2005 RTI"
    },

    "q7": {
        "dense_query": "What is the prescribed period of limitation for institution of a civil suit under the Limitation Act, 1963?",
        "bm25_keywords": "period of limitation institution civil suit schedule Limitation Act 1963 prescribed period"
    },

    "q8": {
        "dense_query": "What is the procedure for a consumer to file a complaint against deficiency of service under the Consumer Protection Act, 2019?",
        "bm25_keywords": "consumer complaint deficiency of service service provider Consumer Protection Act 2019 jurisdiction"
    },
    
}


def main(expanded_flag: Optional[bool]=False):
    
    client = build_client()

    if not client.collection_exists(COLLECTION_NAME):
        print(f"ERROR: collection '{COLLECTION_NAME}' not found. Run embedder_gpu.py first.")
        sys.exit(1)

    info = client.get_collection(COLLECTION_NAME)
    v = info.config.params.vectors
    print(f"Collection: {COLLECTION_NAME}")
    print(f"dims: {v.size}  distance={v.distance}") # type: ignore
    print(f"points: {info.points_count}")
    print(f"Dense model: {DENSE_MODEL_NAME}")
    print(f"Sparse model: {SPARSE_MODEL_NAME}")
    
    if expanded_flag:
        for _, q in QUERIES_EXPANDED.items():
            show_expanded(client, q)
    else:
        if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
            print("\nEnter a query (blank line to exit):")
            while True:
                try:
                    q = input("> ").strip()
                except EOFError:
                    break
                if not q:
                    break
                show(client, q)

        elif len(sys.argv) > 1:
            show(client, " ".join(sys.argv[1:]))

        else:
            for q in test_queries:
                show(client, q)
    client.close()

if __name__ == "__main__":
    expanded_flag: bool = False
    main(expanded_flag)


