
import sqlite3
import pickle

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    VectorParams,
    SparseVectorParams,
    Distance,
    Modifier,
)

SOURCE_DIR = "storage/qdrant_db2"
DESTINATION_URL = "http://localhost:6333"

BATCH_SIZE = 256

client = QdrantClient(url=DESTINATION_URL)


COLLECTION_CONFIGS = {
    "legal_acts": {
        "vectors": {
            "dense": VectorParams(
                size=1024,
                distance=Distance.COSINE,
            )
        },
        "sparse_vectors": {
            "bm25": SparseVectorParams(
                modifier=Modifier.IDF,
            )
        },
    },
    "legal_docs": {
        "vectors": VectorParams(
            size=1024,
            distance=Distance.COSINE,
        ),
        "sparse_vectors": {
            "bm25": SparseVectorParams(
                modifier=Modifier.IDF,
            )
        },
    },
}


def migrate_collection(name: str):

    print(f"\nMigrating {name}...")

    db_path = f"{SOURCE_DIR}/collections/{name}/storage.sqlite"

    conn = sqlite3.connect(
        f"file:{db_path}?mode=ro",
        uri=True,
    )

    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM points"
        ).fetchone()[0]

        print(f"Source points: {total}")

        # Create destination collection
        if client.collection_exists(name):
            raise RuntimeError(
                f"{name} already exists in destination. "
                "Refusing to overwrite."
            )

        config = COLLECTION_CONFIGS[name]

        client.create_collection(
            collection_name=name,
            vectors_config=config["vectors"],
            sparse_vectors_config=config["sparse_vectors"],
        )

        cursor = conn.execute(
            "SELECT point FROM points"
        )

        transferred = 0

        while True:
            rows = cursor.fetchmany(BATCH_SIZE)

            if not rows:
                break

            points = [
                pickle.loads(row[0])
                for row in rows
            ]

            client.upsert(
                collection_name=name,
                points=points,
                wait=True,
            )

            transferred += len(points)

            print(f"Transferred {transferred}/{total}")

        # Verify destination
        destination_count = client.count(
            collection_name=name,
            exact=True,
        ).count

        if destination_count != total:
            raise RuntimeError(
                f"Count mismatch for {name}: "
                f"source={total}, destination={destination_count}"
            )

        print(f"Successfully migrated {name}: {destination_count}")

    finally:
        conn.close()


def main():

    try:
        for name in COLLECTION_CONFIGS:
            migrate_collection(name)

        print("\nAll collections migrated successfully!")

    finally:
        client.close()


if __name__ == "__main__":
    main()



