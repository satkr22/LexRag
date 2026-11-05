from pathlib import Path

import onnxruntime as ort
ort.preload_dlls()  

from qdrant_client import QdrantClient, models
from app.common.config import settings

COLLECTION_NAME = settings.QDRANT_ACTS_COLLECTION_NAME
DENSE_MODEL_NAME = settings.DENSE_MODEL_NAME
SPARSE_MODEL_NAME = settings.SPARSE_MODEL_NAME
QDRANT_URL = settings.QDRANT_URL


def get_act(client: QdrantClient, query: str) -> str | None:
    """
    Executes a hybrid search (Dense + BM25) with Reciprocal Rank Fusion (RRF).
    """
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            # dense search
            models.Prefetch(
                query=models.Document(
                    text=query,
                    model=DENSE_MODEL_NAME,
                    options={"cuda": True, "lazy_load": True}
                ),
                using="dense",
                limit=10
            ),
            # sparse
            models.Prefetch(
                query=models.Document(
                    text=query,
                    model=SPARSE_MODEL_NAME
                ),
                using="bm25",
                limit=10
            )
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=3
    )
    
    print(f"\n--- Query: '{query}' ---")
    if not results.points:
        print("Error: No match found.")
        return None
       
    for i, point in enumerate(results.points):
        code = point.payload.get("act_code") # type: ignore
        print(f"Rank {i+1} | Score: {point.score:.4f} | Act Code: {code}")
        
    return results.points[0].payload.get("act_code") # type: ignore

def main(url):

    client = QdrantClient(
        url=url,
        timeout=120
    )
    
    test_queries = [
        "BNS",                   
        "POCSO act",             
        "Contract act",          
        "income tax code",    
        "right to education 2009", 
        "bhartiya nayay sanhita"
    ]
    
    for q in test_queries:
        get_act(client, q)
        
    client.close()

if __name__ == "__main__":
    main(QDRANT_URL)