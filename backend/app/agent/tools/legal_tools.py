import re
from typing import Optional
from pathlib import Path

from qdrant_client import QdrantClient, models

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.common.config import settings
from app.db.models.toc import TOC
from app.db.models.section import Section
from app.common.act_code_mapping import (
    NAME_ACT_CODE,
    NAME_ACT_CODE_WITHOUT_YEAR,
    ACT_CODE_TO_NAME,
)

CORPUS_COLLECTION_NAME = settings.QDRANT_CORPUS_COLLECTION_NAME
ACTS_COLLECTION_NAME = settings.QDRANT_ACTS_COLLECTION_NAME
DENSE_MODEL_NAME = settings.DENSE_MODEL_NAME
SPARSE_MODEL_NAME = settings.SPARSE_MODEL_NAME
INFERENCE_CUDA = settings.QDRANT_INFERENCE_CUDA

MAX_SECTIONS = 300
ACT_NOT_PRESENT = "act_not_present"


def _clean_act(act: str) -> str:
    if not act:
        return ""

    # strip leading and trailing whitespace
    act = act.strip()

    # attach gaps between words with '-'
    # This catches single spaces, multiple spaces, tabs, and newlines
    act = re.sub(r"\s+", "-", act)

    # replace en dashes, em dashes, and underscores with '-'
    act = act.replace("–", "-")  # en dash
    act = act.replace("—", "-")  # em dash
    act = act.replace("_", "-")  # underscore

    # convert multiple consecutive hyphens into a single hyphen
    act = re.sub(r"-+", "-", act)

    return act.lower()


def _map_act_name_to_code(act: str) -> str:
    if not act:
        return ACT_NOT_PRESENT

    code_form = _clean_act(act)

    name_form = re.sub(r"[\s_–—-]+", " ", act.strip()).strip().lower()

    if code_form in ACT_CODE_TO_NAME:
        return code_form

    if name_form in NAME_ACT_CODE:
        return NAME_ACT_CODE[name_form][0]
    if name_form in NAME_ACT_CODE_WITHOUT_YEAR:
        return NAME_ACT_CODE_WITHOUT_YEAR[name_form][0]

    return ACT_NOT_PRESENT


def _resolve_act(client, act: str) -> Optional[str]:
    code = _map_act_name_to_code(act)
    if code != ACT_NOT_PRESENT:
        return code
    r = get_act(client, act)
    # if r.get("confident") is False:
    #     return None
    return r.get("best") if "error" not in r else None


def view_toc(
    db: Session,
    client: QdrantClient,
    act: str,
    section_range: Optional[tuple[str, str]] = None,
) -> dict:
    """
    Two-stage Table of Content lookup.

    Stage 1  (section_range=None) -> chapters with their (start, end).
    Stage 2  (section_range=(start, end)) -> sections whose chapter covers that range.

    Always call stage 1 first; echo back one of its `section_range` values.
    """

    act = _resolve_act(client, act)  # type: ignore
    if act is None:
        return {
             "error": "Unable to resolve the supplied Act name. Verify the official Act name or use get_act to resolve its code."
        }

    # stage 1: chapters
    if section_range is None:
        stmt = (
            select(
                TOC.chapter_title,
                TOC.chapter_start_section,
                TOC.chapter_end_section,
                func.count(TOC.section_id).label("section_count"),
            )
            .where(TOC.act == act)
            .where(TOC.chapter_start_section.is_not(None))
            .group_by(
                TOC.chapter_title,
                TOC.chapter_start_section,
                TOC.chapter_end_section,
            )
            .order_by(func.min(TOC.section_order))
        )
        rows = db.execute(stmt).all()
        if not rows:
            return {
                "act": act,
                "stage": "chapters",
                "found": False,
                "chapters": [],
                "hint": "This act has no chapter metadata. Use search_sections or get_section(act, section_number) directly.",
            }

        return {
            "act": act,
            "stage": "chapters",
            "hint": "Call again with section_range=(start, end) to see sections.",
            "chapters": [
                {
                    "chapter_title": r.chapter_title,
                    "section_range": [r.chapter_start_section, r.chapter_end_section],
                    "section_count": r.section_count,
                }
                for r in rows
            ],
        }

    # validate
    if (
        not isinstance(section_range, (tuple, list))
        or len(section_range) != 2
        or not all(isinstance(s, str) and s.strip() for s in section_range)
    ):
        return {"error": "section_range must be a (start, end) pair of strings"}

    start, end = (s.strip() for s in section_range)

    # stage 2: section
    stmt = (
        select(
            TOC.section_id,
            TOC.section_number,
            TOC.section_title,
            TOC.chapter_title,
        )
        .where(TOC.act == act)
        .where(TOC.chapter_start_section == start)
        .where(TOC.chapter_end_section == end)
        .order_by(TOC.section_order)
        .limit(MAX_SECTIONS)
    )
    rows = db.execute(stmt).all()

    if not rows:
        return {
            "act": act,
            "stage": "sections",
            "section_range": [start, end],
            "count": 0,
            "hint": "No chapter matches that range. Call without section_range to list chapters.",
            "sections": [],
        }

    return {
        "act": act,
        "stage": "sections",
        "section_range": [start, end],
        "count": len(rows),
        "truncated": len(rows) >= MAX_SECTIONS,
        "chapter_title": rows[0].chapter_title,
        "sections": [
            {
                "section_id": r.section_id,
                "section_number": r.section_number,
                "section_title": r.section_title,
            }
            for r in rows
        ],
    }


def get_section(
    db: Session,
    client: QdrantClient,
    act: str,
    section_number: str,
    section_id: Optional[str] = None,
) -> dict:
    """
    Fetch the full text of one section.

    Pass act + section_number. `section_id` is an optional escape hatch — only
    needed if a previous call returned `ambiguous: true`.
    """

    # by section_id
    if section_id:
        row = db.execute(
            select(Section).where(Section.section_id == section_id)
        ).scalar_one_or_none()
        if row is None:
            return {"error": f"section_id {section_id!r} not found"}
        return _serialize(row)

    section_number = (section_number or "").strip()

    if not section_number:
        return {"error": "section_number is required"}

    act = _resolve_act(client, act)  # type: ignore
    if act is None:
        return {
            "error": "act is not present in corpus or act name is wrong. Try with correct act name or code"
        }

    cleaned = _normalize_section_number(section_number)

    # primary lookup: exact, indexed
    lookup_id = f"{act}_section_{cleaned}"

    row = db.execute(
        select(Section).where(Section.section_id == lookup_id)
    ).scalar_one_or_none()

    if row:
        return _serialize(row)

    rows = (
        db.execute(
            select(Section)
            .where(Section.act == act)
            .where(Section.section_number == cleaned)
            .limit(10)
        )
        .scalars()
        .all()
    )

    if not rows:
        return {
            "act": act,
            "section_number": section_number,
            "found": False,
            "error": (
                "No section matched. Confirm the act name (as listed in the table of content using view_toc tool) "
                "and section number (e.g. '302', '10A')."
            ),
        }

    if len(rows) > 1:
        # Data bug: act + section_number should be unique. Surface.
        return {
            "act": act,
            "section_number": cleaned,
            "ambiguous": True,
            "count": len(rows),
            "hint": "Multiple rows share this act + section_number. Re-call with one of these section_ids.",
            "matches": [
                {
                    "section_id": r.section_id,
                    "section_title": r.section_title,
                    "chapter_title": r.chapter_title,
                }
                for r in rows
            ],
        }

    return _serialize(rows[0])


def _serialize(r: Section) -> dict:
    return {
        "act": r.act,
        "section_id": r.section_id,
        "section_number": r.section_number,
        "section_title": r.section_title,
        "chapter_number": r.chapter_number,
        "chapter_title": r.chapter_title,
        "document_title": r.document_title,
        "content": r.section_content,
        "content_chars": len(r.section_content or ""),
    }


def _normalize_section_number(s: str) -> str:
    """Strip prefixes/punctuation the model sometimes adds: 'Section 302.' -> '302'."""
    s = s.strip()
    for prefix in ("Section ", "section ", "Sec. ", "sec. ", "sec ", "§ "):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :].strip()
            break
    return s.rstrip(" .:;,")


def search_sections(
    client: QdrantClient, query: str, acts_filter: Optional[list[str]] = None
) -> dict:
    """Executes a hybrid search filtered by acts."""

    # payload filter by acts
    category_filter = None
    filtered_acts = []

    if acts_filter is not None and len(acts_filter) > 0:

        for a in acts_filter:
            _a = _resolve_act(client, a)  # type: ignore
            if _a is None:
                return {
                "error": f"Unable to resolve Act filter: {a}",
                "hint": "Correct the Act name or remove the invalid filter."
            }
            filtered_acts.append(_a)

        if filtered_acts:
            category_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="act", match=models.MatchAny(any=filtered_acts)
                    )
                ]
            )

    results = client.query_points(
        collection_name=CORPUS_COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=models.Document(
                    text=query,
                    model=DENSE_MODEL_NAME,
                    options={"cuda": INFERENCE_CUDA, "lazy_load": True},
                ),
                using="",  # this is blank because i have first created dense vector without its label
                limit=10,
                filter=category_filter,  # filter to Dense search
            ),
            models.Prefetch(
                query=models.Document(text=query, model=SPARSE_MODEL_NAME),
                using="bm25",
                limit=10,
                filter=category_filter,  # filter to BM25 search
            ),
        ],
        # Combine the results of both prefetch queries
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=5,
        with_payload=True,
    )

    hits = results.points

    formatted_results = []
    seen_sections = set()

    for hit in hits:
        payload = hit.payload or {}
        metadata = payload.get("metadata", {})

        # extract metadata
        act_code = metadata.get("act", "unknown")
        sec_num = metadata.get("section_number", "unknown")
        sec_title = metadata.get("section_title", "")
        sec_id = metadata.get("section_id", "")
        is_intact = metadata.get("is_intact_section", False)

        # deduplicate
        unique_key = f"{act_code}_{sec_num}"
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
                "act": act_code,
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
        "hint": "If 'is_complete' is False, call get_section using the result's 'act' and 'section_number'. You may also pass its exact 'section_id'.",
    }


def get_act(client: QdrantClient, act_name_query: str) -> dict:
    """
    Executes a hybrid search (Dense + BM25) with Reciprocal Rank Fusion (RRF) to get the act code from the act full name.
    """
    results = client.query_points(
        collection_name=ACTS_COLLECTION_NAME,
        prefetch=[
            # dense search
            models.Prefetch(
                query=models.Document(
                    text=act_name_query,
                    model=DENSE_MODEL_NAME,
                    options={"cuda": INFERENCE_CUDA, "lazy_load": True},
                ),
                using="dense",
                limit=10,
            ),
            # sparse
            models.Prefetch(
                query=models.Document(text=act_name_query, model=SPARSE_MODEL_NAME),
                using="bm25",
                limit=10,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=3,
        with_payload=True,
    )

    if not results.points:
        return {
            "error": "act is not present in corpus or act name is wrong. Try with rephrased act name."
        }

    res = results.points[0]
    
    matches = [
        {
            "act_code": p.payload.get("act_code"), # type: ignore
            "score": round(float(p.score), 2)
        } for p in results.points if p.payload.get("act_code") # type: ignore
    ]
    
    if not matches:
        return {"error": "act not found."}
    
    gap = matches[0]["score"] - matches[1]["score"] if len(matches) > 1 else 1.0
    
    return {
        "matches": matches,
        "best": matches[0]["act_code"],
        # "confident": gap >= 0.15 or matches[0]["score"] >= 0.95,
}

