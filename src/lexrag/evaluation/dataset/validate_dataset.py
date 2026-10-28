import json, asyncio
from pathlib import Path


def load_titles(path):
    f_path = Path(__file__).parent.parent / "data_ingestion" / "parsed" / "aaalll" / path
    
    with open(f_path) as f:
        return [{"id": s["id"], "title": s["article"]["title"]} for s in json.load(f)]

bns  = load_titles("bns_sections.json")    
bnss = load_titles("bnss_sections.json")   
bsa  = load_titles("bsa_sections.json")

all_valid = [t["id"] for lst in [bns, bnss, bsa] for t in lst]
print("total_ids:", len(all_valid))

PATH_TO_DATASET = Path(__file__).parent / "questions" / "question_dataset.json"

with open(PATH_TO_DATASET, "r") as f:
    out = json.load(f)

unique = set()
   
valid = 0
invalid = 0
for o in out:
    for id in o["referenced_sections"]:
        if id in all_valid:
            valid += 1
            unique.add(id)
        else:
            invalid += 1
            
print("valid ids:", valid)
print("invalid ids:", invalid)
print("unique ids:", len(unique))