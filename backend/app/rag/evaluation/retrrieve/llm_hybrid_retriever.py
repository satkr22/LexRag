import asyncio
import json
import os
import time
from pathlib import Path

import onnxruntime as ort
ort.preload_dlls()


from qdrant_client import QdrantClient, models

from backend.app.rag.retrieval.query_llm.query import generate_response_gemini, generate_response_qwen, generate_response_deepseek
from backend.app.rag.retrieval.query_llm.data_models import QueryResponse, EnrichedQuery



QUESTION_JSON = Path(__file__).parent.parent / "dataset" / "questions" / "question_dataset.json"
OUTPUT_JSON   = Path(__file__).parent.parent / "ragas" / "data" / "ragas_evaluation_dataset_llm.json"

COLLECTION_NAME   = "legal_docs"
DENSE_MODEL_NAME  = "BAAI/bge-large-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"
DB_PATH           = "./qdrant_db2"
TOP_K             = 5

LLM_MODEL         = "gemini-3.1-flash-lite"
LLM_CONCURRENCY   = 8      # tune to your RPM
LLM_MAX_RETRIES   = 4


# ---------- Qdrant ----------

def build_client() -> QdrantClient:
    return QdrantClient(
        path=DB_PATH,
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider"],
    )


def warmup(client: QdrantClient) -> None:
    """Force-load the ONNX embedders once so no query pays the load cost."""
    client.query_points(
        collection_name=COLLECTION_NAME,
        query=models.Document(text="warmup", model=DENSE_MODEL_NAME),
        using="",
        limit=1,
    )
    client.query_points(
        collection_name=COLLECTION_NAME,
        query=models.Document(text="warmup", model=SPARSE_MODEL_NAME),
        using="bm25",
        limit=1,
    )


def hybrid_search(
    client: QdrantClient,
    query_text: EnrichedQuery,
    category_ids: list,
    limit: int = 5,
):
    t0 = time.perf_counter()

    category_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="category_id",
                match=models.MatchAny(any=category_ids),
            )
        ]
    )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=models.Document(text=query_text.dense_query, model=DENSE_MODEL_NAME),
                using="",
                limit=limit * 2,
            ),
            models.Prefetch(
                query=models.Document(text=query_text.bm25_keywords, model=SPARSE_MODEL_NAME),
                using="bm25",
                limit=limit * 2,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=category_filter,      # <-- was missing in your original
        limit=limit,
        with_payload=True,
    )
    return results.points, time.perf_counter() - t0



async def route_query(
    question: str,
    sem: asyncio.Semaphore,
) -> QueryResponse: # type: ignore
    """Bounded-concurrency async LLM call with retry."""
    async with sem:
        for attempt in range(LLM_MAX_RETRIES):
            try:
                # resp = await generate_response_qwen(question)
                # resp = await generate_response_gemini(question)
                resp = await generate_response_deepseek(question)
                return resp
            except Exception as e:
                if attempt == LLM_MAX_RETRIES - 1:
                    raise
                wait = 2 ** attempt
                print(f"[llm retry {attempt + 1}/{LLM_MAX_RETRIES}] "
                      f"{type(e).__name__}: {e}  -> sleeping {wait}s")
                await asyncio.sleep(wait)


def _split_hits(hits):
    sections, contexts = [], []
    for point in hits:
        payload = point.payload or {}
        text = payload.get("text")
        if text:
            contexts.append(text.strip())
        sid = payload.get("section_id")
        if sid and sid not in sections:
            sections.append(sid)
    return sections, contexts


async def process_one(
    item: dict,
    qdrant: QdrantClient,
    sem: asyncio.Semaphore,
    search_lock: asyncio.Lock,
    progress: dict,
) -> dict:
    question = item["question"]

    # LLM — concurrent across questions
    t_llm0 = time.perf_counter()
    routed: QueryResponse = await route_query(question, sem)
    t_llm = time.perf_counter() - t_llm0

    # RAG — serialized (Qdrant local is not thread-safe) but off the event loop
    async with search_lock:
        hits, t_search = await asyncio.to_thread(
            hybrid_search, qdrant, routed.enriched_query, routed.category_ids, TOP_K
        )

    sections, contexts = _split_hits(hits)

    progress["done"] += 1
    n = progress["done"]
    if n % 10 == 0 or n == progress["total"]:
        print(f"[{n}/{progress['total']}] llm={t_llm:.2f}s search={t_search:.2f}s")

    return {
        "question": question,
        "retrieved_sections": sections,
        "retrieved_context": contexts,
        "referenced_sections": item.get("referenced_sections", []),
        "referenced_context": item.get("referenced_context", ""),
    }



async def main() -> None:
    qdrant = build_client()

    if not qdrant.collection_exists(COLLECTION_NAME):
        print(f"ERROR: collection '{COLLECTION_NAME}' not found.")
        return

    warmup(qdrant)

    try:
        with open(QUESTION_JSON, "r", encoding="utf-8") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {QUESTION_JSON} not found.")
        return

    sem = asyncio.Semaphore(LLM_CONCURRENCY)
    search_lock = asyncio.Lock()
    progress = {"done": 0, "total": len(dataset)}

    print(f"Processing {len(dataset)} questions "
          f"(llm concurrency={LLM_CONCURRENCY}, top_k={TOP_K})...")

    t0 = time.perf_counter()
    results = await asyncio.gather(*[
        process_one(item, qdrant, sem, search_lock, progress)
        for item in dataset
    ])
    elapsed = time.perf_counter() - t0

    print(f"\nDone in {elapsed:.1f}s "
          f"({elapsed / len(dataset):.2f}s/question)")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"Exported {len(results)} records to {OUTPUT_JSON}")


if __name__ == "__main__":
    asyncio.run(main())