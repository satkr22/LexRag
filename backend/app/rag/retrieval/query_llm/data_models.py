from pydantic import BaseModel, Field
from typing import List


class EnrichedQuery(BaseModel):
    dense_query: str = Field(
        description="A natural-language, semantically rich query for dense/vector search as per given user query."
    )
    bm25_keywords: str = Field(
        description="Space-separated keywords optimized for BM25/lexical search as per given user query."
    )

class QueryResponse(BaseModel):
    requires_retrieval: bool = Field(
        description="Set to True ONLY if the user query is a legal question or problem requiring reference law lookups. Set to False for generic greetings, garbage, out-of-scope text, or simple conversation."
    )
    
    category_ids: List[str] = Field(
        description="List of category IDs (e.g., CAT_001, CAT_002) that best match the user's query. Select ALL relevant categories from the given category dictionary."
    )
    enriched_query: EnrichedQuery = Field(
        description="The enriched search query split into dense and keyword forms."
    )