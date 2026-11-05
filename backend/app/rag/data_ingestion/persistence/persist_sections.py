
import json
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal_corpus
from app.db.init_db import init_db_corpus
from backend.app.db.corpus_models.section import Section


def push_records(
    input_dir: Path,
    batch_size: int = 500,
) -> None:


    session = SessionLocal_corpus()
    total = 0

    try:
        for file in input_dir.iterdir():

            if not file.is_file() or file.suffix.lower() != ".json":
                continue

            with open(file, "r", encoding="utf-8") as f:
                raw = json.load(f)

            if not isinstance(raw, list):
                raise ValueError("JSON root must be a list of objects")

            print(f"Loaded {len(raw)} records from {file}")

            for start in range(0, len(raw), batch_size):
                batch = raw[start:start + batch_size]
                now = datetime.now(timezone.utc)

                records = [
                    {
                        "act": row["metadata"]["act"],
                        "section_id": row["metadata"]["id"],
                        "section_content": row["article"]["content"],
                        "section_number": row["article"]["number"],
                        "section_title": row["article"]["title"],
                        "chapter_number": row["heading"]["number"],
                        "chapter_title": row["heading"]["title"],
                        "chapter_section_range": row["heading"]["range"],
                        "category_id": row["metadata"]["category_id"],
                        "category_code": row["metadata"]["category_code"],
                        "category_label": row["metadata"]["category_label"],
                        "document_title": row["metadata"]["document_title"],
                        "created_at": now,
                        "updated_at": now,
                    }
                    for row in batch
                ]

                stmt = insert(Section).values(records)

                stmt = stmt.on_conflict_do_update(
                    index_elements=[Section.section_id],
                    set_={
                        "act": stmt.excluded.act,
                        "section_content": stmt.excluded.section_content,
                        "section_number": stmt.excluded.section_number,
                        "section_title": stmt.excluded.section_title,
                        "chapter_number": stmt.excluded.chapter_number,
                        "chapter_title": stmt.excluded.chapter_title,
                        "chapter_section_range": stmt.excluded.chapter_section_range,
                        "category_id": stmt.excluded.category_id,
                        "category_code": stmt.excluded.category_code,
                        "category_label": stmt.excluded.category_label,
                        "document_title": stmt.excluded.document_title,
                        "updated_at": now,
                    },
                )

                session.execute(stmt)
                session.commit()

                total += len(batch)
                print(f"Processed {total}/{len(raw)} records")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()
        print(f"Done. Processed {total} records.")
