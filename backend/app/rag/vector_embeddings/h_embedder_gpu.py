import json
import uuid
from pathlib import Path

import onnxruntime as ort
ort.preload_dlls()  

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance
from fastembed import SparseTextEmbedding
from fastembed import TextEmbedding

COLLECTION_NAME = "legal_docs"
DENSE_MODEL_NAME = "BAAI/bge-large-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"

def generate_deterministic_uuid(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

def index_chunks_with_fastembed(client: QdrantClient, json_file_path: str):
    
    with open(json_file_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks. beginning vectorization...")

    # Prepare points array to upsert
    points = []
    
    for chunk in chunks:
        payload = {
            "text": chunk["text"],
            "chunk_id": chunk["chunk_id"],
            "section_id": chunk["section_id"],
            "token_count": chunk["token_count"]
        }
        payload.update(chunk.get("metadata", {}))
    
        points.append(   
            models.PointStruct(
                id=generate_deterministic_uuid(chunk["chunk_id"]),
                vector={
                    "dense": models.Document(
                        text=chunk["text"],
                        model=DENSE_MODEL_NAME,
                        options={"cuda": True, "lazy_load": True},
                    ),
                    "bm25": models.Document(
                        text=chunk["text"],
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
    print(f"Successfully indexed all {len(chunks)} chunks of doc {json_file_path} into Qdrant.")
    

def main(input_dir: Path, db_path: Path):
    
    # CUDA (GPU)
    client = QdrantClient(
        path=str(db_path), 
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider"]
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
    
    json_files = [p.name for p in input_dir.iterdir() if p.is_file()]
    
    for file in json_files:
        input_json_path = input_dir / file
        index_chunks_with_fastembed(client, str(input_json_path))
    
    client.close()

if __name__ == "__main__":
    
    INPUT_DIR = Path(__file__).parent.parent / "data_ingestion" / "chunked" / "aaalll"
    VECTOR_DB_PATH = Path(__file__).parents[4] / "qdrant_db"
    
    main(INPUT_DIR, VECTOR_DB_PATH)