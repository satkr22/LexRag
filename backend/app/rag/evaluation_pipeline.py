import asyncio
from pathlib import Path

from app.rag.evaluation.dataset.make_dataset import make_dataset
from app.rag.evaluation.retrrieve.hybrid_retriever import main as retriever
from app.rag.evaluation.ragas.evaluate_comprehensive import main as evaluate

DATASET_FILE = Path(__file__).parent / "evaluation" / "ragas" / "data" / "ragas_evaluation_dataset.json"
MAIN_OUTPUT = Path(__file__).parent / "evaluation" / "ragas"  / "result" / "evaluation_results.json"


async def main():
    print("\nMaking dataset for evaluation...")
    await make_dataset()
    print("\nDataset created.")
    
    
    print("\nRetrieveing the results for test questions...")
    retriever()
    print("\nRetrieval done.")
    
    print("\nStarting evaluation of answers...")
    await evaluate(str(DATASET_FILE), str(MAIN_OUTPUT))
    print("\nEvaluation done.")
    
    print("\n\nEvaluation Pipeline Completed.\n")
    
if __name__ == "__main__":
    asyncio.run(main())