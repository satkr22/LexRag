import re
import json
from typing import Any
from qdrant_client import AsyncQdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding

from langchain_core.runnables import Runnable
from langchain_core.messages import SystemMessage, HumanMessage

from app.common.config import settings
from app.rag.retrieval.query_llm.data_models import QueryResponse, EnrichedQuery


COLLECTION_NAME = settings.QDRANT_CORPUS_COLLECTION_NAME
TOP_K = 5


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


def _build_system_prompt() -> str:
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

Return a JSON object matching this exact json structure:
    {{
        "category_ids": [..],
        "enriched_query": {{
            "dense_query": "A complete semantic search query.",
            "bm25_keywords": "keyword1 keyword2 keyword3"
        }}
    }}
"""

async def _hybrid_search(
    client: AsyncQdrantClient, 
    dense_model: TextEmbedding,
    sparse_model: SparseTextEmbedding,
    query_text: EnrichedQuery, 
    category_ids: list,
    limit: int = TOP_K
):
    """Executes a hybrid search filtered by category IDs(if provided) using Reciprocal Rank Fusion."""
    
    # client-side(python application server) vector embeddings generation
    
    dense_vector = next(dense_model.embed([query_text.dense_query])).tolist() # type: ignore
    
    raw_sparse = next(sparse_model.embed([query_text.bm25_keywords])) # type: ignore
    
    sparse_vector = models.SparseVector(
        indices=raw_sparse.indices.tolist(),
        values=raw_sparse.values.tolist()
    )
    
    category_filter = None
    if category_ids:
        category_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="category_id", 
                    match=models.MatchAny(any=category_ids) 
                )
            ]
        )
    respone = await client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=dense_vector,
                using="",
                limit=limit * 2,
                filter=category_filter,
            ),
            models.Prefetch(
                query=sparse_vector,
                using="bm25",
                limit=limit * 2,
                filter=category_filter,
            ),
        ],
       
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True
    )
    
    return respone.points


def _format_hits(hits: list, query: str) -> dict[str, Any]:
    
    formatted_results = []
    seen_sections = set()

    for hit in hits:
        payload = hit.payload or {}

        # extract metadata
        act_code = payload.get("act", "unknown")
        sec_num = payload.get("section_number", "unknown")
        sec_title = payload.get("section_title", "")
        sec_id = payload.get("section_id", "")
        is_intact = payload.get("is_intact_section", False)

        # deduplicate
        unique_key = sec_id
        if unique_key in seen_sections:
            continue
        seen_sections.add(unique_key)

        # clean the text: remove "[Act: ... ]" header
        raw_text = payload.get("text", "")
        clean_text = re.sub(r"^\[.*?\]\s*", "", raw_text, flags=re.DOTALL).strip()

        # truncation based on "is_intact_section"
        if is_intact:
            # chunk IS the section. return full text.
            snippet = clean_text
            is_complete = True
        else:
            # chunk is a fragment. truncate to save tokens.
            snippet = clean_text
            if len(snippet) > 1000:
                snippet = snippet[:1000].rsplit(" ", 1)[0] + "..."
            is_complete = False

        formatted_results.append(
            {
                "act_code": act_code,
                "section_id": sec_id,
                "section_number": sec_num,
                "section_title": sec_title,
                "is_complete": is_complete,
                "text": snippet,
            }
        )

    return {
        "query": query,
        "count": len(formatted_results),
        "results": formatted_results,
        "hint": "If 'is_complete' is False, call get_section using the result's 'act_code' and 'section_number' and 'section_id'.",
    }


async def retrieve(
    query: str, 
    client: AsyncQdrantClient, 
    dense_model: TextEmbedding, 
    sparse_model: SparseTextEmbedding, 
    llm_runnable: Runnable
) -> dict[str, Any]:
    
    prompt = _build_system_prompt()
    
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=query)
    ]
    
    try:
        result: QueryResponse = await llm_runnable.ainvoke(messages)
        print(result)
    except Exception as e:
        # log this error 
        # raise ValueError(f"llm response fail: {e}")
        result = QueryResponse(
            category_ids=[],
            enriched_query=EnrichedQuery(
                dense_query=query,
                bm25_keywords=query
            )
        )
    try:
        hits = await _hybrid_search(client, dense_model, sparse_model, result.enriched_query, result.category_ids, TOP_K)
        formatted_result = _format_hits(hits, query)
        return formatted_result
    except Exception as e:
        return {"query": query}
    
        # add this error to log
        # raise ValueError(f"Qdrant retrieval fail: {e}")
