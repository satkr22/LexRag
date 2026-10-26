import json
import uuid
from pathlib import Path

from qdrant_client import QdrantClient, models
from fastembed import SparseTextEmbedding

COLLECTION_NAME = "legal_docs"
SPARSE_MODEL_NAME = "Qdrant/bm25"

def generate_deterministic_uuid(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

def append_sparse_vectors(client: QdrantClient, json_file_path: str, sparse_model: SparseTextEmbedding):
    
    with open(json_file_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    texts = [chunk["text"] for chunk in chunks]
    ids = [generate_deterministic_uuid(chunk["chunk_id"]) for chunk in chunks]

    print(f"Generating BM25 vectors for {len(texts)} chunks in {Path(json_file_path).name}...")
    
    embeddings = list(sparse_model.embed(texts))

    points = []
    for point_id, embedding in zip(ids, embeddings):
        points.append(
            models.PointVectors(
                id=point_id,
                vector={
                    "bm25": models.SparseVector(
                        indices=embedding.indices.tolist(),
                        values=embedding.values.tolist()
                    )
                }
            )
        )

    
    client.update_vectors(
        collection_name=COLLECTION_NAME,
        points=points
    )
    print(f"Successfully appended sparse vectors for {json_file_path}")

if __name__ == "__main__":
    INPUT_DIR = Path(__file__).parent.parent / "data_ingestion" / "chunked" / "aaalll"
    db_path: str = "./qdrant_db2"
    
    client = QdrantClient(path=db_path)
    
    print("appending sparse vectors schema to collection schema...")
    client.create_vector_name(
        collection_name=COLLECTION_NAME,
        vector_name="bm25",
        vector_name_config=models.SparseVectorNameConfig(
            sparse=models.SparseVectorConfig(
                modifier=models.Modifier.IDF
            )
        )
    )
    
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    
    json_files = [p.name for p in INPUT_DIR.iterdir() if p.is_file()]
    
    for file in json_files:
        input_json_path = INPUT_DIR / file
        append_sparse_vectors(client, str(input_json_path), sparse_model)

    client.close()