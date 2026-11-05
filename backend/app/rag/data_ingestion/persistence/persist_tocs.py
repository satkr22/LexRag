
import json
from pathlib import Path
from itertools import groupby
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal_corpus
from app.db.init_db import init_db_corpus
from app.db.corpus_models.toc import TOC


def generate_toc(json_filepath):
    with open(json_filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    sorted_data = sorted(data, key=lambda x: x["metadata"]["order"])

    toc_records = []

    for heading_title, group in groupby(
        sorted_data,
        key=lambda x: x["metadata"]["heading_title"],
    ):
        sections = list(group)

        first_sec = sections[0]["metadata"]["article_number"]
        last_sec = sections[-1]["metadata"]["article_number"]

        computed_range = (
            f"{first_sec}-{last_sec}"
            if first_sec != last_sec
            else f"s. {first_sec}"
        )

        for sec in sections:
            toc_records.append({
                "act": sec["metadata"]["act"],
                "heading_title": heading_title,
                "computed_heading_range": computed_range,
                "heading_start": first_sec,
                "heading_end": last_sec,
                "section_number": sec["metadata"]["article_number"],
                "section_title": sec["metadata"]["article_title"],
                "section_id": sec["metadata"]["id"],
                "order": sec["metadata"]["order"],
            })

    return toc_records


def push_toc(
    input_dir: Path,
    batch_size: int = 500,
) -> None:


    session = SessionLocal_corpus()
    total = 0

    try:
        for file in input_dir.iterdir():

            if not file.is_file() or file.suffix.lower() != ".json":
                continue

            rows = generate_toc(file)

            for start in range(0, len(rows), batch_size):
                batch = rows[start:start + batch_size]
                now = datetime.now(timezone.utc)

                records = [
                    {
                        "act": row["act"],
                        "chapter_title": row["heading_title"],
                        "chapter_section_range": row["computed_heading_range"],
                        "chapter_start_section": row["heading_start"],
                        "chapter_end_section": row["heading_end"],
                        "section_number": row["section_number"],
                        "section_title": row["section_title"],
                        "section_id": row["section_id"],
                        "section_order": row["order"],
                        "created_at": now,
                        "updated_at": now,
                    }
                    for row in batch
                ]

                stmt = insert(TOC).values(records)

                stmt = stmt.on_conflict_do_update(
                    index_elements=[TOC.section_id],
                    set_={
                        "act": stmt.excluded.act,
                        "chapter_title": stmt.excluded.chapter_title,
                        "chapter_section_range": stmt.excluded.chapter_section_range,
                        "chapter_start_section": stmt.excluded.chapter_start_section,
                        "chapter_end_section": stmt.excluded.chapter_end_section,
                        "section_number": stmt.excluded.section_number,
                        "section_title": stmt.excluded.section_title,
                        "section_order": stmt.excluded.section_order,
                        "updated_at": now,
                    },
                )

                session.execute(stmt)
                session.commit()

                total += len(batch)
                print(f"Processed {total}/{len(rows)} records")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()
        print(f"Done. Processed {total} records.")
