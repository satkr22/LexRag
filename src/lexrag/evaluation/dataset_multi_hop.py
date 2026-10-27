import json, asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="YOUR_KEY")

def load_titles(path):
    with open(path) as f:
        return [{"id": s["id"], "title": s["article"]["title"]} for s in json.load(f)]

bns  = load_titles("bns_sections.json")    # 358
bnss = load_titles("bnss_sections.json")   # 531
bsa  = load_titles("bsa_sections.json")    # 170

PROMPT = """You are given section titles from two Indian criminal statutes.
{pair_desc}

ACT A sections:
{list_a}

ACT B sections:
{list_b}

Generate {n} multi-hop questions. Each question MUST require reading at least
one section from ACT A AND one section from ACT B to answer. Do not create
questions answerable from a single section. Do not mention section numbers
in the question. Prefer questions where the two sections play complementary
roles (offence + procedure, offence + evidence, definition + consequence).

Return strict JSON array:
[{{"question": "...", "referenced_section": ["id_a", "id_b"], "answer": "..."}}]
"""

async def gen_pair(list_a, list_b, n, pair_desc):
    def fmt(lst):
        return "\n".join(f"{t['id']}: {t['title']}" for t in lst)
    prompt = PROMPT.format(
        pair_desc=pair_desc,
        list_a=fmt(list_a),
        list_b=fmt(list_b),
        n=n,
    )
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    data = json.loads(resp.choices[0].message.content)
    return data if isinstance(data, list) else data.get("questions", [])

async def main():
    batches = [
        (bns,  bnss, 20, "BNS = offences, BNSS = criminal procedure"),
        (bns,  bsa,  15, "BNS = offences, BSA = evidence rules"),
        (bnss, bsa,  15, "BNSS = procedure, BSA = evidence rules"),
    ]

    all_valid = {t["id"] for lst, _, _, _ in batches for t in lst}
    out, seen = [], set()

    for a, b, n, desc in batches:
        print(f"generating {n} for {desc} ...")
        rows = await gen_pair(a, b, n, desc)
        for r in rows:
            q = r["question"].strip()
            ids = [i for i in r["referenced_section"] if i in all_valid]
            # must reference at least one section from each side
            ids_a = [i for i in ids if i.startswith("bns_") or (a is bns and i.startswith("bns_"))]
            has_a = any(i in {t["id"] for t in a} for i in ids)
            has_b = any(i in {t["id"] for t in b} for i in ids)
            if not (q and has_a and has_b) or q in seen:
                continue
            seen.add(q)
            out.append({
                "question": q,
                "referenced_section": ids,
                "referneced_context": r["answer"].strip(),
            })
        print(f"  kept so far: {len(out)}")

    json.dump(out, open("multihop_dataset.json", "w"), ensure_ascii=False, indent=2)
    print(f"\nWrote {len(out)} rows")

asyncio.run(main())