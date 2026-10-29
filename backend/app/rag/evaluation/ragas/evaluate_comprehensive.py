import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd  # Added dependency for seamless tabular CSV conversion
from ragas.metrics.collections import ContextRecall
from ragas.llms import llm_factory
from openai import AsyncOpenAI


DATASET_FILE = Path(__file__).parent / "data" / "ragas_evaluation_dataset.json"
MAIN_OUTPUT = Path(__file__).parent / "result" / "evaluation_results.json"

LOGS_BACKUP_FILE = Path(__file__).parent / "result" / "evaluation_rows_live.jsonl"
FINAL_CSV_OUTPUT = Path(__file__).parent / "result" / "evaluation_rows_comprehensive.csv"


client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://ws-n7c4pdh4ldno9hkc.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
)

EVALUATOR_LLM = llm_factory(
    model="deepseek-v4.1-flash-1017", 
    provider="openai", 
    client=client,
    extra_body={
        "reasoning_effort": "low", 
        "temperature": 0.0,
        "max_tokens": 4092
    }
)

def load_dataset(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_id_based_recall(retrieved_ids: List[Any], reference_ids: List[Any]) -> float:
    if not reference_ids:
        return 0.0
    intersection = set(retrieved_ids) & set(reference_ids)
    return len(intersection) / len(set(reference_ids))


def calculate_id_based_precision(retrieved_ids: List[Any], reference_ids: List[Any]) -> float:
    if not retrieved_ids or not reference_ids:
        return 0.0
    score = 0.0
    hits = 0
    ref_set = set(reference_ids)
    
    for i, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in ref_set:
            hits += 1
            score += hits / i
            
    if hits == 0:
        return 0.0
    return score / min(len(ref_set), len(retrieved_ids))


def hit_at_k(retrieved: List[str], relevant: set, k: int) -> int:
    return int(any(d in relevant for d in retrieved[:k]))


def reciprocal_rank(retrieved: List[str], relevant: set) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


async def run_comprehensive_evaluation(
    dataset: List[Dict[str, Any]],
    output_file: str,
    max_concurrent_requests: int = 10
) -> Dict[str, float]:
    
    metric = ContextRecall(llm=EVALUATOR_LLM)
    sem = asyncio.Semaphore(max_concurrent_requests)
    
    LOGS_BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    completed_questions = {}
    if LOGS_BACKUP_FILE.exists():
        print(f"Found existing progress backup file at {LOGS_BACKUP_FILE}. Scanning for cached rows...")
        with open(LOGS_BACKUP_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        cached_row = json.loads(line)
                        completed_questions[cached_row["question"]] = cached_row
                    except Exception:
                        pass
        print(f"Skipping {len(completed_questions)} already evaluated rows detected on disk.")

    async def worker(entry: Dict[str, Any]):
        question = entry["question"]
    
        if question in completed_questions:
            return completed_questions[question]
            
        retrieved_ids = entry.get("retrieved_sections", [])
        reference_ids = entry.get("referenced_sections", [])
        relevant_set = set(reference_ids)
        
        id_recall = calculate_id_based_recall(retrieved_ids, reference_ids)
        id_precision = calculate_id_based_precision(retrieved_ids, reference_ids)
        hit_5 = hit_at_k(retrieved_ids, relevant_set, k=5)
        mrr_score = reciprocal_rank(retrieved_ids, relevant_set)
        
        context_recall_llm = 0.0
        
        # Execute asynchronous model-as-a-judge tracking
        async with sem:
            data = {
                "user_input": question,
                "retrieved_contexts": entry.get("retrieved_context", []),
                "reference": entry.get("referenced_context", ""),
            }
            try:
                result = await metric.ascore(**data)
                context_recall_llm = float(result) if isinstance(result, (int, float)) else getattr(result, 'value', 0.0)
            except Exception as e:
                print(f"Error evaluating LLM context recall for row: {question[:40]}... -> {e}")
                context_recall_llm = np.nan 

        row_payload = {
            "question": question,
            "id_based_context_recall": id_recall,
            "id_based_context_precision": id_precision,
            "hit_at_5": hit_5,
            "mrr": mrr_score,
            "context_recall_llm": context_recall_llm
        }
        
        with open(LOGS_BACKUP_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row_payload) + "\n")
            
        return row_payload

    tasks = [worker(entry) for entry in dataset]
    print(f"Launching {len(tasks)} tasks concurrently (Max Concurrency: {max_concurrent_requests})...")
    
    evaluated_rows = await asyncio.gather(*tasks)
    
    df = pd.DataFrame(evaluated_rows)
    df.to_csv(FINAL_CSV_OUTPUT, index=False, encoding="utf-8")
    print(f"row results saved into Pandas table structure: {FINAL_CSV_OUTPUT}")
    
    summary_aggregates = {
        "id_based_context_recall": float(df["id_based_context_recall"].mean()),
        "id_based_context_precision": float(df["id_based_context_precision"].mean()),
        "hit_at_5": float(df["hit_at_5"].mean()),
        "mrr": float(df["mrr"].mean()),
        "context_recall_llm": float(df["context_recall_llm"].dropna().mean())
    }
    
    return summary_aggregates


async def main(dataset_path: str, output_file: str) -> None:
    dataset = load_dataset(dataset_path)

    global_results = await run_comprehensive_evaluation(
        dataset=dataset,
        output_file=output_file,
        max_concurrent_requests=10
    )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(global_results, f, indent=2)

    print(f"\nAll metrics saved to {output_file}")
    print(json.dumps(global_results, indent=2))
    

if __name__ == "__main__":
    asyncio.run(
        main(
            dataset_path=str(DATASET_FILE),
            output_file=str(MAIN_OUTPUT),
        )
    )
