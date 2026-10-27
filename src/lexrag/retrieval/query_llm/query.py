import os
import json
import dotenv

from openai import OpenAI
from google import genai
from google.genai import types

from src.lexrag.retrieval.query_llm.data_models import QueryResponse


dotenv.load_dotenv()


CATEGORY = {
    "CAT_001": {
        "label": "Constitutional, Governance & Access to Justice",
        "description": (
            "Constitutional law, fundamental rights, constitutional institutions, "
            "government accountability, transparency, access to justice, legal aid, "
            "and the protection and enforcement of human rights. Includes laws governing "
            "the powers and functions of government bodies, citizens' constitutional "
            "protections, access to public information, and legal assistance."
        ),
    },

    "CAT_002": {
        "label": "Criminal Law, Procedure & Evidence",
        "description": (
            "Substantive criminal law defining offences, criminal liability, punishments, "
            "and defences; criminal investigation, police powers, arrest, bail, prosecution, "
            "criminal trials, and sentencing; and the admissibility, relevance, and proof "
            "of evidence in judicial proceedings. Also includes laws addressing specific "
            "criminal offences, corruption, atrocities, and special criminal enforcement "
            "procedures."
        ),
    },

    "CAT_003": {
        "label": "Civil Procedure, Remedies & Dispute Resolution",
        "description": (
            "Civil litigation, jurisdiction of civil courts, institution and conduct of "
            "civil suits, pleadings, interim relief, execution of decrees, limitation periods, "
            "civil remedies, consumer disputes, arbitration, mediation-related legal "
            "frameworks, and other mechanisms for resolving non-criminal disputes. "
            "Includes laws governing civil claims, enforcement of rights, and remedies "
            "available to individuals, consumers, and businesses."
        ),
    },

    "CAT_004": {
        "label": "Contracts, Commerce & Corporate Law",
        "description": (
            "Formation, interpretation, performance, breach, and enforcement of contracts; "
            "commercial transactions, sale of goods, negotiable instruments, partnerships, "
            "limited liability partnerships, companies, corporate governance, business "
            "obligations, insolvency, bankruptcy, restructuring, and creditor-debtor "
            "relationships. Includes laws governing commercial rights, business entities, "
            "financial obligations, and corporate disputes."
        ),
    },

    "CAT_005": {
        "label": "Family, Marriage & Succession",
        "description": (
            "Marriage, marital validity, divorce, judicial separation, matrimonial rights, "
            "family relationships, maintenance within family-law frameworks, adoption or "
            "related family matters where applicable, inheritance, succession, wills, "
            "testamentary dispositions, and distribution of estates. Includes laws governing "
            "personal status, family disputes, and the transfer of property following death."
        ),
    },

    "CAT_006": {
        "label": "Property, Registration & Easements",
        "description": (
            "Ownership, transfer, sale, mortgage, lease, gift, and other transactions "
            "involving immovable property; registration of documents and instruments; "
            "property interests, rights of way, easements, and related rights and "
            "obligations. Includes laws governing legally recognized interests in property "
            "and the formalities required to create, transfer, or record those interests."
        ),
    },

    "CAT_007": {
        "label": "Taxation",
        "description": (
            "Direct and indirect taxation, tax liability, assessment, computation of taxable "
            "income, deductions, exemptions, tax collection, filing and compliance, goods "
            "and services tax, input tax credit, tax refunds, tax authorities, appeals, "
            "penalties, and tax-related offences. Includes laws governing the imposition, "
            "administration, recovery, and dispute resolution of taxes."
        ),
    },

    "CAT_008": {
        "label": "Digital, Cyber & Data Protection",
        "description": (
            "Electronic records, electronic signatures, digital transactions, cybercrime, "
            "unauthorized access to computer systems, cybersecurity-related legal "
            "obligations, intermediary liability, digital communications, personal data "
            "processing, consent, data principal rights, data fiduciary obligations, "
            "and personal data protection. Includes laws regulating activities, rights, "
            "duties, and offences arising from the use of information technology and "
            "digital systems."
        ),
    },

    "CAT_009": {
        "label": "Social Protection, Child Rights & Education",
        "description": (
            "Legal protections and welfare measures for children, women, persons with "
            "disabilities, senior citizens, and other protected or vulnerable groups. "
            "Includes child sexual abuse prevention, juvenile justice, domestic violence, "
            "dowry-related protections, disability rights, maintenance and welfare of "
            "senior citizens, children's right to education, and related safeguarding, "
            "welfare, rehabilitation, and institutional obligations."
        ),
    },

    "CAT_010": {
        "label": "Transport & Road Safety",
        "description": (
            "Motor vehicles, vehicle registration, driving licences, traffic regulation, "
            "road safety, driver and vehicle-owner obligations, road accidents, motor "
            "vehicle insurance, compensation for accident victims, traffic offences, "
            "penalties, and regulatory responsibilities relating to road transport."
        ),
    },
}



def build_system_prompt() -> str:
    return f"""

You are an expert legal query routing agent. Your objective is to classify a user's legal query and optimize it for a hybrid search engine (Vector + BM25).

<taxonomy>
{json.dumps(CATEGORY, indent=2)}
</taxonomy>

### INSTRUCTIONS
1. Analyze the user's query against the <taxonomy> provided above.
2. Select relevant category IDs only. You must only use IDs that explicitly exist in the taxonomy. 
3. Generate the dense_query: Rewrite the user's query into a clear, full-sentence semantic search string. Expand on implied legal context, concepts, or synonyms to improve vector embedding similarity. NOT too verbose.
4. Generate the bm25_keywords: Extract the core legal terms, entities, and actions. Output as a space-separated string, stripping all stop-words and filler words.

### OUTPUT REQUIREMENTS

Return a JSON object matching this exact structure:
    (
        "category_ids": [..],
        "enriched_query": (
            "dense_query": "A complete semantic search query.",
            "bm25_keywords": "keyword1 keyword2 keyword3"
        )
    )


"""


def generate_response_gemini(query: str):

    system_prompt = build_system_prompt()

    user_query = query

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # call with structured output
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=user_query,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=QueryResponse,  
            temperature=0.1,
        ),
    )
    
    result: QueryResponse = response.parsed #type: ignore
    
    return result


def generate_response_qwen(query: str):
    
    system_prompt = build_system_prompt()
    
    user_query = query
    
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://ws-n7c4pdh4ldno9hkc.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    )

    response = client.responses.parse(
        # model="deepseek-v4.1-flash-1017",
        model="qwen3.8-2.4t-a95b",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        text_format=QueryResponse,
        temperature=0.1,
    )
    
    result: QueryResponse = response.output_parsed # type: ignore
    
    return result



if __name__ == "__main__":

    user_query = "My landlord is refusing to return my security deposit after I moved out. What legal options do I have?"
    response = generate_response_gemini(user_query)
    result: QueryResponse = response.parsed # type: ignore
    
    print(f"Selected Categories: {result.category_ids}")
    print(f"Dense Query: {result.enriched_query.dense_query}")
    print(f"BM25 Keywords: {result.enriched_query.bm25_keywords}")