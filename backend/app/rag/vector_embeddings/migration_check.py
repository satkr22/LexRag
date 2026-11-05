

from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

print("Discovered collections:", client.get_collections())
for col in ["legal_acts", "legal_docs"]:
    try:
        status = client.get_collection(collection_name=col)
        print(f"Collection '{col}' total vectors: {status.points_count}")
    except Exception as e:
        print(f"Could not load '{col}': {e}")


# for name in ["legal_acts", "legal_docs"]:
#     points, _ = client.scroll(
#         collection_name=name,
#         limit=1,
#         with_vectors=True,
#     )

#     point = points[0]

#     print(f"\n{name}")
#     print("Vector type:", type(point.vector))
#     print("Vector keys:", list(point.vector.keys()) if isinstance(point.vector, dict) else "Unnamed dense vector")
#     print("Sparse vectors:", point.vector.get("bm25") if isinstance(point.vector, dict) and "bm25" in point.vector else "Check separately")

#     print("Sparse vector field:", point.vector)

client.close()