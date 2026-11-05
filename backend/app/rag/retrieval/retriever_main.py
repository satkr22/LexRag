import re

from langchain_core.runnables import Runnable
from qdrant_client import AsyncQdrantClient, models

from app.common.config import settings
from app.rag.retrieval.query_llm.data_models import QueryResponse, EnrichedQuery



COLLECTION_NAME = settings.QDRANT_CORPUS_COLLECTION_NAME
DENSE_MODEL = settings.DENSE_MODEL_NAME
SPARSE_MODEL = settings.SPARSE_MODEL_NAME
DB_PATH = settings.QDRANT_URL
INFERENCE_CUDA = settings.QDRANT_INFERENCE_CUDA
TOP_K = 5



async def _hybrid_search(
    client: AsyncQdrantClient, 
    query_text: EnrichedQuery, 
    category_ids: list,
    limit: int = TOP_K
):
    """Executes a hybrid search filtered by category IDs(if provided) using Reciprocal Rank Fusion."""
    
    category_filter = None
    if category_ids:
        category_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="category_id", 
                    match=models.MatchAny(any=category_ids) 
                )
            ]
        )
    respone = await client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=models.Document(
                    text=query_text.dense_query, 
                    model=DENSE_MODEL,
                    options={"cuda": INFERENCE_CUDA, "lazy_load": True},
                ),
                using="",
                limit=limit * 2,
                filter=category_filter,
            ),
            models.Prefetch(
                query=models.Document(
                    text=query_text.bm25_keywords, 
                    model=SPARSE_MODEL
                ),
                using="bm25",
                limit=limit * 2,
                filter=category_filter,
            ),
        ],
       
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True
    )
    
    hits = respone.points
    return hits


def _format_hits(hits: list, query: str):
    
    formatted_results = []
    seen_sections = set()

    for hit in hits:
        payload = hit.payload or {}
        metadata = payload.get("metadata", {})

        # extract metadata
        act_code = metadata.get("act", "unknown")
        sec_num = metadata.get("section_number", "unknown")
        sec_title = metadata.get("section_title", "")
        sec_id = metadata.get("section_id", "")
        is_intact = metadata.get("is_intact_section", False)

        # deduplicate
        unique_key = sec_id
        if unique_key in seen_sections:
            continue
        seen_sections.add(unique_key)

        # clean the text: remove "[Act: ... ]" header
        raw_text = payload.get("text", "")
        clean_text = re.sub(r"^\[.*?\]\s*", "", raw_text, flags=re.DOTALL).strip()

        # truncation based on "is_intact_section"
        if is_intact:
            # chunk IS the section. return full text.
            snippet = clean_text
            is_complete = True
        else:
            # chunk is a fragment. truncate to save tokens.
            snippet = clean_text
            if len(snippet) > 1000:
                snippet = snippet[:1000].rsplit(" ", 1)[0] + "..."
            is_complete = False

        formatted_results.append(
            {
                "act_code": act_code,
                "section_id": sec_id,
                "section_number": sec_num,
                "section_title": sec_title,
                "is_complete": is_complete,
                "text": snippet,
            }
        )

    return {
        "query": query,
        "count": len(formatted_results),
        "results": formatted_results,
        "hint": "If 'is_complete' is False, call get_section using the result's 'act_code' and 'section_number' and 'section_id'.",
    }


async def retrieve(query: str, client: AsyncQdrantClient, llm_runnable: Runnable):
    try:
        result: QueryResponse = await llm_runnable.ainvoke(query)
    except Exception:
        result = QueryResponse(
            category_ids=[],
            enriched_query=EnrichedQuery(
                dense_query=query,
                bm25_keywords=query
            )
        )
    try:
        hits = await _hybrid_search(client, result.enriched_query, result.category_ids, TOP_K)
        formatted_result = _format_hits(hits, query)
        return formatted_result
    
    except Exception as e:
        raise ValueError(f"Qdrant retrieval fail: {e}")
