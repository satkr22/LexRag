import json
import asyncio
from pathlib import Path

from dataset import main
from lexrag.evaluation.dataset.dataset_multi_hop import main as m_h_main


OUTPUT_PATH = Path(__file__).parent / "questions" / "question_dataset.json"

INPUT_PATH = Path(__file__).parent / "questions"



async def make_dataset():
    main()
    await m_h_main()
    
    c = []
    
    p1 = INPUT_PATH / "eval_dataset.json"
    with open("p1", "r") as f1:
        c1 = json.load(f1)
        c.append(c1)
        
    p2 = INPUT_PATH / "eval_multi_hop_dataset.json"
    with open("p2", "r") as f2:
        c2 = json.load(f2)
        c.append(c2)
        
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(c, f)
  

if __name__ == "__main__":
    asyncio.run(make_dataset())