import json
import random
from collections import defaultdict
from pathlib import Path
from datasets import load_dataset


print("Loading GSMS-B ...")
ds = load_dataset(
    "GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA", 
    data_files="bns_bnss_bsa_combined_legal_qa.jsonl",
    split="train"
)
all_rows = list(ds)

print(len(ds))
# print(list(ds)[:5])

for act in ["BNS 2023", "BNSS 2023", "BSA 2023"]:
    bns_act_rows = [r for r in all_rows if r["act"] == act] # type: ignore
    print(len(bns_act_rows))