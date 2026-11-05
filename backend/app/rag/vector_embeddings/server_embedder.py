
import json
import uuid
from pathlib import Path

import onnxruntime as ort
ort.preload_dlls()

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance

COLLECTION_NAME = "legal_docs"

DENSE_MODEL_NAME = "BAAI/bge-large-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"

QDRANT_URL = "http://localhost:6333"


def generate_deterministic_uuid(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


def index_chunks_with_fastembed(
    client: QdrantClient,
    json_file_path: str
):

    with open(json_file_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks. Beginning vectorization...")

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
                        options={
                            "cuda": True,
                            "lazy_load": True,
                        },
                    ),
                    "bm25": models.Document(
                        text=chunk["text"],
                        model=SPARSE_MODEL_NAME,
                    )
                },
                payload=payload,
            )
        )

    client.upload_points(
        collection_name=COLLECTION_NAME,
        points=points,
        batch_size=64,
        parallel=1,
        wait=True,
    )

    print(
        f"Successfully indexed {len(chunks)} chunks "
        f"from {json_file_path} into Qdrant."
    )


def main(input_dir: Path):

    # Connect to Docker-hosted Qdrant server
    client = QdrantClient(
        url=QDRANT_URL,
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider"],
        timeout=120,
    )

    if not client.collection_exists(COLLECTION_NAME):

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

    else:
        print(f"Collection '{COLLECTION_NAME}' already exists.")

    json_files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".json"
    )

    for input_json_path in json_files:
        index_chunks_with_fastembed(
            client,
            str(input_json_path),
        )

    info = client.get_collection(COLLECTION_NAME)

    print("\nIndexing completed.")
    print("Total points:", info.points_count)

    client.close()


if __name__ == "__main__":

    INPUT_DIR = (
        Path(__file__).parent.parent
        / "data_ingestion"
        / "chunked"
        / "aaalll"
    )

    main(INPUT_DIR)
