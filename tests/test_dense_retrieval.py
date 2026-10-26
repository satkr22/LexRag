import sys
import time
from pathlib import Path

import onnxruntime as ort
ort.preload_dlls()

from qdrant_client import QdrantClient, models

COLLECTION_NAME = "legal_docs"
MODEL_NAME      = "BAAI/bge-large-en-v1.5"
DB_PATH         = "./qdrant_db2"
TOP_K           = 5

def build_client() -> QdrantClient:
    return QdrantClient(
        path=DB_PATH,
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider"],
    )

def search(client: QdrantClient, query: str, top_k: int = TOP_K):
    t0 = time.perf_counter()
    result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=models.Document(
            text=query,
            model=MODEL_NAME,
            options={"cuda": True, "lazy_load": True},
        ),
        limit=top_k,
        with_payload=True,
    )
    return result.points, time.perf_counter() - t0

def format_hit(rank: int, point) -> str:
    p = point.payload or {}
    text = (p.get("text") or "").replace("\n", " ").strip()
    snippet = text[:220] + ("..." if len(text) > 220 else "")
    return (
        f"  [{rank}] score={point.score:.4f}  "
        f"section={p.get('section_id', '?')}  "
        f"chunk={p.get('chunk_id', '?')}  "
        f"tokens={p.get('token_count', '?')}\n"
        f"      {snippet}"
    )

def show(client: QdrantClient, query: str, top_k: int = TOP_K):
    print(f"\n=== Query: {query!r}")
    hits, elapsed = search(client, query, top_k)
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

def main():
    
    client = build_client()

    if not client.collection_exists(COLLECTION_NAME):
        print(f"ERROR: collection '{COLLECTION_NAME}' not found. Run embedder_gpu.py first.")
        sys.exit(1)

    info = client.get_collection(COLLECTION_NAME)
    v = info.config.params.vectors
    print(f"Collection: {COLLECTION_NAME}")
    print(f"dims: {v.size}  distance={v.distance}") # type: ignore
    print(f"points: {info.points_count}")
    print(f"model: {MODEL_NAME}")

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
        for q in QUERIES:
            show(client, q)

    client.close()

if __name__ == "__main__":
    main()