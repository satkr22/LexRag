import json
import random
from collections import defaultdict
from pathlib import Path
from datasets import load_dataset


SEED         = 42
N_PER_ACT    = 50
ACTS         = ["BNS 2023", "BNSS 2023", "BSA 2023"]
ACT_KEY_MAP  = {"BNS 2023": "bns", "BNSS 2023": "bnss", "BSA 2023": "bsa"}

OUTPUT_PATH = Path(__file__).parent / "dataset" / "eval_dataset.json"




def stratified_sample_by_section(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    
    by_section: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_section[str(r["section_number"])].append(r)

    sections = list(by_section.keys())
    rng.shuffle(sections)

    picked: list[dict] = []
    used_ids: set[int] = set()

    # pass 1: at most 1 question per section
    for sec in sections:
        if len(picked) >= n:
            break
        q = rng.choice(by_section[sec])
        picked.append(q)
        used_ids.add(id(q))

    # pass 2: if not enough sections
    if len(picked) < n:
        pool = [r for r in rows if id(r) not in used_ids]
        rng.shuffle(pool)
        picked.extend(pool[: n - len(picked)])

    return picked




def main() -> None:
    rng = random.Random(SEED)

    print("Loading GSMS-B ...")
    ds = load_dataset(
        "GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA", 
        data_files="bns_bnss_bsa_combined_legal_qa.jsonl",
        split="train"
    )
    
    all_rows = list(ds)
    print(f"  {len(all_rows)} total rows")

    output: list[dict] = []
    seen_questions: set[str] = set()
    q_no = 0
    for act in ACTS:
        act_rows = [r for r in all_rows if r["act"] == act] # type: ignore
        print(f"\n[{act}] {len(act_rows)} rows available")

        picked: list[dict] = []
        max_attempts = 5
        attempt = 0
        while len(picked) < N_PER_ACT and attempt < max_attempts:
            attempt += 1
            candidates = stratified_sample_by_section(act_rows, N_PER_ACT * 3, rng) # type: ignore
            for c in candidates:
                if len(picked) >= N_PER_ACT:
                    break
                q_text = c["question"].strip()
                if q_text in seen_questions:
                    continue
                picked.append(c)
                seen_questions.add(q_text)

        if len(picked) < N_PER_ACT:
            print(f"  [WARN] only {len(picked)}/{N_PER_ACT} had local section text")

        for c in picked:
            ref_id = f"{ACT_KEY_MAP[act]}_section_{c['section_number']}"
            q_no += 1
            output.append({
                "q_no": q_no,
                "question": c["question"].strip(),
                "referenced_section": [ref_id],
                "referenced_context": c["answer"].strip(), 
            })

    # sanity
    assert len(output) == 150, f"expected 150 got {len(output)}"
    acts_count = defaultdict(int)
    for row in output:
        acts_count[row["referenced_section"][0].split("_")[0]] += 1
    print(f"\nFinal counts: {dict(acts_count)}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(output)} rows -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()