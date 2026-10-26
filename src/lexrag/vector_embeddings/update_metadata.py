import json
import uuid
from pathlib import Path
from collections import defaultdict

from qdrant_client import QdrantClient

COLLECTION_NAME = "legal_docs"
DB_PATH = "./qdrant_db2"

INPUT_DIR = (
    Path(__file__).parent.parent/ "data_ingestion" / "chunked" / "aaalll"
)


def generate_deterministic_uuid(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


def update_metadata():
    client = QdrantClient(path=DB_PATH)
    updated = 0
    skipped = 0

    try:
        for json_file in INPUT_DIR.glob("*.json"):
            with open(json_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)

            # Group chunks that would share the same category_id
            groups = defaultdict(list)

            for chunk in chunks:
                metadata = chunk.get("metadata", {})

                if "category_id" not in metadata or "category_code" not in metadata:
                    skipped += 1
                    continue

                point_id = generate_deterministic_uuid(
                    chunk["chunk_id"]
                )

                key = (
                    metadata["category_id"],
                    metadata["category_code"],
                )
                groups[key].append(point_id)

            for (category_id, category_code), point_ids in groups.items():
                
                for start in range(0, len(point_ids), 256):
                    batch = point_ids[start:start + 256]

                    client.set_payload(
                        collection_name=COLLECTION_NAME,
                        payload={
                            "category_id": category_id,
                            "category_code": category_code,
                        },
                        points=batch,
                        wait=True,
                    )

                    updated += len(batch)

            print(f"Processed: {json_file.name}")

        print(f"Updated points: {updated}")
        print(f"Skipped chunks (missing metadata): {skipped}")

    finally:
        client.close()


if __name__ == "__main__":
    update_metadata()