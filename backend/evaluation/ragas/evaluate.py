import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from ragas import EvaluationDataset, evaluate, RunConfig
from ragas.metrics.collections import ContextRecall
from ragas.llms import llm_factory

from openai import AsyncOpenAI


DATASET_FILE_LLM = Path(__file__).parent / "data" / "ragas_evaluation_dataset_llm.json"
MAIN_OUTPUT_LLM = Path(__file__).parent / "result" / "evaluation_results_llm.json"

DATASET_FILE = Path(__file__).parent / "data" / "ragas_evaluation_dataset.json"
MAIN_OUTPUT = Path(__file__).parent / "result" / "evaluation_results.json"


RUN_CONFIG = RunConfig(max_workers=4, timeout=120, max_retries=3)
client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://ws-n7c4pdh4ldno9hkc.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
)
EVALUATOR_LLM = llm_factory(
    model="deepseek-v4.1-flash-1017", 
    provider="openai", 
    client=client,
    extra_body={
        "reasoning_effort": 10, # range: 1-100 for deepseek models
        "temperature": 0.0
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


def run_id_based_metrics(dataset: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculates ID-based metrics locally without deprecated Ragas wrappers."""
    recalls = []
    precisions = []
    
    for entry in dataset:
        retrieved = entry.get("retrieved_sections", [])
        reference = entry.get("referenced_sections", [])
        
        recalls.append(calculate_id_based_recall(retrieved, reference))
        precisions.append(calculate_id_based_precision(retrieved, reference))
        
    return {
        "id_based_context_recall": float(np.mean(recalls)),
        "id_based_context_precision": float(np.mean(precisions)),
    }


def hit_at_k(retrieved: List[str], relevant: set, k: int) -> int:
    return int(any(d in relevant for d in retrieved[:k]))


def reciprocal_rank(retrieved: List[str], relevant: set) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def run_hit_mrr(dataset: List[Dict[str, Any]], k: int = 5) -> Dict[str, float]:
    hits, rrs = [], []
    for entry in dataset:
        retrieved = entry.get("retrieved_sections", [])
        relevant = set(entry.get("referenced_sections", []))
        hits.append(hit_at_k(retrieved, relevant, k))
        rrs.append(reciprocal_rank(retrieved, relevant))
    return {f"hit_at_{k}": float(np.mean(hits)), "mrr": float(np.mean(rrs))}


async def run_context_recall(
    dataset: List[Dict[str, Any]],
    output_file: str,
    max_concurrent_requests: int = 10
) -> float:
    
    metric = ContextRecall(llm=EVALUATOR_LLM)
    
    sem = asyncio.Semaphore(max_concurrent_requests)
    
    async def worker(entry: Dict[str, Any]):
        # async with sem: forces the code to wait if max capacity is reached
        async with sem:
            data = {
                "user_input": entry["question"],
                "retrieved_contexts": entry.get("retrieved_context", []),
                "reference": entry.get("referenced_context", ""),
            }
            try:
                result = await metric.ascore(**data)
                return float(result) if isinstance(result, (int, float)) else getattr(result, 'value', 0.0)
            except Exception as e:
                print(f"Error evaluating row: {e}")
                return 0.0
    
    tasks = [worker(entry) for entry in dataset]
    
    print(f"Launching {len(tasks)} tasks concurrently (Max Concurrency Bound: {max_concurrent_requests})...")
    
    # fire all tasks into the event loop at once
    extracted_scores = await asyncio.gather(*tasks)
    
    mean_score = float(np.mean(extracted_scores)) if extracted_scores else 0.0
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"context_recall_llm": mean_score}, f, indent=2)
        
    print(f"Context-recall (llm) -> {mean_score:.4f} (Saved to {output_file})")
    return mean_score


async def main(
    dataset_path: str,
    output_file: str,
    recall_variant: str | None = None,
) -> None:
    dataset = load_dataset(dataset_path)

    results: Dict[str, Any] = {}
    results.update(run_id_based_metrics(dataset))
    results.update(run_hit_mrr(dataset, k=5))

    if recall_variant is not None:
        score = await run_context_recall(
            dataset,
            output_file=f"context_recall_{recall_variant}.json",
        )
        results[f"context_recall_{recall_variant}"] = score

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nAll results saved to {output_file}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":

    asyncio.run(
        main(
            dataset_path=str(DATASET_FILE),
            output_file=str(MAIN_OUTPUT),
            # dataset_path=str(DATASET_FILE_LLM),
            # output_file=str(MAIN_OUTPUT_LLM),
            recall_variant="llm",
        )
    )
    