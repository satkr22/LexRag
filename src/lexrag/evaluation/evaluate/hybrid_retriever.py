import json
import time
from pathlib import Path
from typing import Optional

import onnxruntime as ort
ort.preload_dlls()

from qdrant_client import QdrantClient, models


QUESTION_JSON = Path(__file__).parent.parent / "dataset" / "questions" / "question_dataset.json"
OUTPUT_JSON = Path(__file__).parent.parent / "ragas" / "data" / "ragas_evaluation_dataset.json"


COLLECTION_NAME = "legal_docs"
DENSE_MODEL_NAME = "BAAI/bge-large-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"
DB_PATH = "./qdrant_db2"
TOP_K = 5 


def build_client() -> QdrantClient:
    return QdrantClient(
        path=DB_PATH,
        local_inference_batch_size=16,
        local_inference_providers=["CUDAExecutionProvider"],
    )

def hybrid_search(client: QdrantClient, query_text: str, limit: int = 5):
    
    t0 = time.perf_counter()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=models.Document(text=query_text, model=DENSE_MODEL_NAME),
                using="", 
                limit=limit * 2, 
            ),
            models.Prefetch(
                query=models.Document(text=query_text, model=SPARSE_MODEL_NAME),
                using="bm25",
                limit=limit * 2,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True
    )
    return results.points, time.perf_counter() - t0

def main():
    client = build_client()

    if not client.collection_exists(COLLECTION_NAME):
        print(f"ERROR: collection '{COLLECTION_NAME}' not found.")
        return

    # Load the baseline questions and references
    input_file = QUESTION_JSON
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: The file {input_file} was not found.")
        return

    ragas_eval_data = []

    print(f"Processing {len(dataset)} questions for RAGAS evaluation...")

    for i, item in enumerate(dataset):
        question = item["question"]
        
        hits, elapsed_time = hybrid_search(client, question, limit=TOP_K)
        
        retrieved_sections = []
        retrieved_context = []
        
        
        for point in hits:
            payload = point.payload or {}
        
            text_chunk = payload.get("text")
            if text_chunk:
                retrieved_context.append(text_chunk.strip())
            
            section_id = payload.get("section_id")
            if section_id and section_id not in retrieved_sections:
                retrieved_sections.append(section_id)
                
        eval_record = {
            "question": question,
            "retrieved_sections": retrieved_sections,
            "retrieved_context": retrieved_context,
            "referenced_sections": item.get("referenced_sections", []),
            "referenced_context": item.get("referenced_context", "")
        }
        
        ragas_eval_data.append(eval_record)
        
        if (i + 1) % 10 == 0:
            print(f"Processed {i + 1}/{len(dataset)} questions...")

    
    output_file = OUTPUT_JSON
    with open(output_file, "w", encoding="utf-8") as out_f:
        json.dump(ragas_eval_data, out_f, indent=4, ensure_ascii=False)
        
    print(f"\nSuccessfully completed. Exported {len(ragas_eval_data)} records to {output_file}.")

if __name__ == "__main__":
    main()