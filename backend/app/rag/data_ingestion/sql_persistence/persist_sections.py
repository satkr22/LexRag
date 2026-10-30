from pathlib import Path
import json
from datetime import datetime, timezone

from app.db.session import SessionLocal_corpus
from app.db.init_db import init_db_corpus
from app.models_db.section import Section


def push_records(
    input_dir: Path,
    batch_size: int = 500,
) -> None:
    
    init_db_corpus()
    
    session = SessionLocal_corpus()
    total = 0
    
    try:
        for file in input_dir.iterdir():
            
            with open(file, "r", encoding="utf-8") as f:
                raw = json.load(f)

            if not isinstance(raw, list):
                raise ValueError("JSON root must be a list of objects")

            print(f"Loaded {len(raw)} records from {file}")

            
            for start in range(0, len(raw), batch_size):
                batch = raw[start : start + batch_size]
                
                
                # existing_ids = set(
                #     session.scalars(
                #         select(Section.section_id).where(
                #             Section.section_id.in_(
                #                 [row["metadata"]["id"] for row in batch]
                #             )
                #         )
                #     ).all()
                # )
                
                c = 0
                for row in batch:
                    # section_id = row["metadata"]["id"]
                    # if section_id in existing_ids:
                    #     continue
                    section = Section(
                        act=row["metadata"]["act"],
                        section_id=row["metadata"]["id"],
                        section_content=row["article"]["content"],
                        section_number=row["article"]["number"],
                        section_title=row["article"]["title"],
                        chapter_number=row["heading"]["number"],
                        chapter_title=row["heading"]["title"],
                        chapter_section_range=row["heading"]["range"],
                        category_id=row["metadata"]["category_id"],
                        category_code=row["metadata"]["category_code"],
                        category_label=row["metadata"]["category_label"],
                        document_title=row["metadata"]["document_title"],
                        created_at=datetime.now(timezone.utc),                   
                        updated_at=datetime.now(timezone.utc)                   
                    )
                    session.add(section)
                    c += 1
            
                session.commit()

                total += c
                print(f"  batch {start // batch_size + 1}: pushed {total}/{len(raw)}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        print(f"Done. Processed {total} records.")


if __name__ == "__main__":
    
    INPUT_PATH = Path(__file__).parent.parent / "parsed" / "aaalll"
    
    push_records(
        INPUT_PATH,
        batch_size=500
    )