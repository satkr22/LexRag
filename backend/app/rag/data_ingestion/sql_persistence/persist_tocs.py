import json
from pathlib import Path
from itertools import groupby
from datetime import datetime, timezone

from app.db.session import SessionLocal_corpus
from app.db.init_db import init_db_corpus
from app.models_db.toc import TOC



def generate_toc(json_filepath):
    with open(json_filepath, 'r') as f:
        data = json.load(f)

    sorted_data = sorted(data, key=lambda x: x['metadata']['order'])

    toc_records = []
    
    for heading_title, group in groupby(sorted_data, key=lambda x: x['metadata']['heading_title']):
        sections = list(group)
        
        first_sec = sections[0]['metadata']['article_number']
        last_sec = sections[-1]['metadata']['article_number']
        computed_range = f"{first_sec}-{last_sec}" if first_sec != last_sec else f"s. {first_sec}"
        
        for sec in sections:
            toc_records.append({
                "act": sec['metadata']['act'],
                "heading_title": heading_title,
                "computed_heading_range": computed_range,
                "section_number": sec['metadata']['article_number'],
                "section_title": sec['metadata']['article_title'],
                "section_id": sec['metadata']['id']
            })
            
    return toc_records


def push_toc(
    input_dir: Path,
    batch_size: int = 500,
) -> None:
    
    init_db_corpus()
    
    session = SessionLocal_corpus()
    total = 0
    
    try:
        for file in input_dir.iterdir():
            
            rows = generate_toc(file)
                        
            for start in range(0, len(rows), batch_size):
                
                batch = rows[start : start + batch_size]
                c = 0
                for row in batch:
                    toc = TOC(
                        act=row["act"],
                        chapter_title=row["heading_title"],
                        chapter_section_range=row["computed_heading_range"],
                        section_number=row["section_number"],
                        section_title=row["section_title"],
                        section_id=row["section_id"],
                        created_at=datetime.now(timezone.utc),                   
                        updated_at=datetime.now(timezone.utc)                   
                    )
                    session.add(toc)
                    c += 1
            
                session.commit()

                total += c
                print(f"  batch {start // batch_size + 1}: pushed {total}/{len(rows)}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        print(f"Done. Processed {total} records.")


if __name__ == "__main__":
    
    INPUT_PATH = Path(__file__).parent.parent / "parsed" / "aaalll"
    
    push_toc(
        INPUT_PATH,
        batch_size=500
    )