import uuid
from pathlib import Path

import onnxruntime as ort
ort.preload_dlls()  

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance

from app.common.act_code_mapping import ACT_CODE_TO_NAME
from app.common.config import settings


COLLECTION_NAME = settings.QDRANT_ACTS_COLLECTION_NAME
DENSE_MODEL_NAME = settings.DENSE_MODEL_NAME
SPARSE_MODEL_NAME = settings.SPARSE_MODEL_NAME
QDRANT_URL = settings.QDRANT_URL


def generate_deterministic_uuid(act_code: str, act_name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{act_code}::{act_name}"))


def index_acts_with_fastembed(client: QdrantClient):
    
    # Prepare points array to upsert
    points = []

    for act_code, act_name in ACT_CODE_TO_NAME.items():
        
        payload = {"act_code": act_code}
        
        to_embed = f"{act_code} {act_name}"
        
        points.append(   
            models.PointStruct(
                id=generate_deterministic_uuid(act_code, act_name),
                vector={
                    "dense": models.Document(
                        text=to_embed,
                        model=DENSE_MODEL_NAME,
                        options={"cuda": True, "lazy_load": True},
                    ),
                    "bm25": models.Document(
                        text=to_embed,
                        model=SPARSE_MODEL_NAME,
                    )
                },
                payload=payload,
            ) 
        )
        
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )    
    print(f"Successfully indexed all {len(ACT_CODE_TO_NAME)} acts into Qdrant.")


def main(url):
    
    # CUDA (GPU)
    client = QdrantClient(
        url=url,
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider", "CPUExecutionProvider"] if settings.QDRANT_INFERENCE_CUDA else None,
        timeout=120,
    )
        
    if not client.collection_exists(collection_name=COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": models.VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                ),
            },
        )
        print(f"Collection '{COLLECTION_NAME}' created successfully.")
    
    index_acts_with_fastembed(client)
    
    client.close()

if __name__ == "__main__":
    main(QDRANT_URL)
