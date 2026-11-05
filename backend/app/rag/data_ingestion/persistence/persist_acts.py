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
VECTOR_DB_PATH = settings.QDRANT_URL


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
        url=settings.QDRANT_URL,
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
    main(
        Path(VECTOR_DB_PATH).resolve()
    )



















# from datetime import datetime, timezone

# from app.db.session import SessionLocal_corpus
# from app.db.init_db import init_db_corpus
# from app.db.models.act import Act
# from app.common.act_code_mapping import ACT_CODE_TO_NAME


# def get_acts():
#     acts: list[dict[str, str]] = []
#     for act_code, name in ACT_CODE_TO_NAME.items():
#         acts.append({act_code: name})
#     return acts


# def push_acts(
#     batch_size: int = 500,
# ) -> None:
    
#     init_db_corpus()
    
#     session = SessionLocal_corpus()
#     total = 0
    
#     try:
#         rows = get_acts()
                    
#         for start in range(0, len(rows), batch_size):
            
#             batch = rows[start : start + batch_size]
#             c = 0
#             # print(batch)
#             for row in batch:
#                 act_code, act_name = list(row.items())[0]
#                 act = Act(
#                     act_code=act_code.lower(),
#                     act_name=act_name.lower(),
#                     created_at=datetime.now(timezone.utc),                   
#                     updated_at=datetime.now(timezone.utc)                   
#                 )
#                 session.add(act)
#                 c += 1
        
#             session.commit()

#             total += c
#             print(f"  batch {start // batch_size + 1}: pushed {total}/{len(rows)}")

#     except Exception:
#         session.rollback()
#         raise
#     finally:
#         session.close()
#         print(f"Done. Processed {total} records.")


# if __name__ == "__main__":
    
#     push_acts(batch_size=500)