import os
import dotenv
import json, asyncio
from pathlib import Path
from pydantic import BaseModel, Field

from openai import AsyncOpenAI
from google import genai
from google.genai import types

dotenv.load_dotenv()

class DataSet(BaseModel):
    question: str = Field(description="multi-hop question")
    referenced_sections: list[str] = Field(description="list of ids of referenced sections")
    answer: str = Field(description="answer of the question based on the legal text")

class QueryResponse(BaseModel):
    q_objects: list[DataSet] = Field(description="list of structured objects")
    
    
client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://ws-n7c4pdh4ldno9hkc.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",                     
)

g_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def load_titles(path):
    f_path = Path(__file__).parent.parent / "data_ingestion" / "parsed" / "aaalll" / path
    
    with open(f_path) as f:
        return [{"id": s["id"], "title": s["article"]["title"]} for s in json.load(f)]

bns  = load_titles("bns_sections.json")    
bnss = load_titles("bnss_sections.json")   
bsa  = load_titles("bsa_sections.json")

PROMPT = """You are given section titles from two Indian criminal statutes.
Abbreviatons:
BNS: Bharatiya Nyaya Sanhita, 2023
BNSS: Bharatiya Nagarik Suraksha Sanhita, 2023
BSA: Bharatiya Sakshya Adhiniyam, 2023 

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
[{{"question": "...", "referenced_sections": ["id_a", "id_b"], "answer": "..."}}]
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
    

    response = g_client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QueryResponse,  
            temperature=0.6,
        ),
    )
    result: QueryResponse = response.parsed # type: ignore

    return result

async def main():
    batches = [
        (bnss, bsa, 15, "BNSS = procedure, BSA = evidence rules"),
        (bns, bsa, 15, "BNS = offences, BSA = evidence rules"),
        (bns, bnss, 20, "BNS = offences, BNSS = criminal procedure"),
    ]

    out, seen = [], set()
    for a, b, n, desc in batches:
        print(f"generating {n} for {desc} ...")
        
        rows = await gen_pair(a, b, n, desc)
        
        for r in rows.q_objects:
            out.append({
                "question": r.question,
                "referenced_section": r.referenced_sections,
                "referneced_context": r.answer.strip(),
            })

        print(f"  kept so far: {len(out)}")

    all_valid = [t["id"] for lst in [bns, bnss, bsa] for t in lst]
    
    valid = 0
    invalid = 0
    for o in out:
        for id in o["referenced_section"]:
            if id in all_valid:
                valid += 1
            else:
                invalid += 1
                
    print("valid ids:", valid)
    print("invalid ids:", invalid)
    
    json.dump(out, open("multihop_dataset.json", "w"), ensure_ascii=False, indent=2)
    
    
    print(f"\nWrote {len(out)} rows")

asyncio.run(main())