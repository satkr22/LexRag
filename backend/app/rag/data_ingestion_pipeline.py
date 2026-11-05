
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.session import engine_corpus
from app.common.config import settings

from app.rag.data_ingestion.web_scrapper.scrap import main as scrapper
from app.rag.data_ingestion.parser.parse_html import main as parser
from app.rag.data_ingestion.parser.merge_sections import merge_section
from app.rag.data_ingestion.chunker.chunk import process_corpus as chunker
from app.rag.vector_embeddings.server_embedder import main as embedder
from app.rag.data_ingestion.persistence.persist_sections import push_records
from app.rag.data_ingestion.persistence.persist_tocs import push_toc
from app.rag.data_ingestion.persistence.persist_acts import main as embed_acts


SCRAPPED_OUTPUT = Path(__file__).parent / "data_ingestion" / "scrapped"
PARSED_OUTPUT = Path(__file__).parent / "data_ingestion" / "parsed"
MERGE_OUTPUT = Path(__file__).parent / "data_ingestion" / "parsed" / "aaalll"
CHUNKED_OUTPUT = Path(__file__).parent / "data_ingestion" / "chunked"
EMBEDDER_INPUT = Path(__file__).parent / "data_ingestion" / "chunked" / "aaalll"

QDRANT_URL = settings.QDRANT_URL

CORPUS_ALEMBIC_CONFIG = Path(__file__).resolve().parents[2] / "alembic-corpus.ini"


def initialize_corpus_database():
    print("\nChecking PostgreSQL corpus database...")

    with engine_corpus.connect() as connection:
        database_info = connection.execute(
            text("""
                SELECT current_database(),
                       current_user,
                       inet_server_addr(),
                       inet_server_port()
            """)
        ).one()

    print(f"Connected to corpus database: {database_info[0]}")
    print(f"Database user: {database_info[1]}")
    print(f"PostgreSQL server: {database_info[2]}:{database_info[3]}")

    print("\nRunning Alembic migrations...")

    if not CORPUS_ALEMBIC_CONFIG.exists():
        raise FileNotFoundError(
            f"Alembic configuration not found: {CORPUS_ALEMBIC_CONFIG}"
        )

    alembic_config = Config(str(CORPUS_ALEMBIC_CONFIG))
    command.upgrade(alembic_config, "head")

    print("Corpus database migrations completed.")


def main():
    # Database initialization must happen before ingestion.
    initialize_corpus_database()

    print("\nStarted Scrapping from web...")
    scrapper(SCRAPPED_OUTPUT)
    print("\nScrapping done.")

    print("\nStarted Parsing scrapped html...")
    parser(SCRAPPED_OUTPUT, PARSED_OUTPUT)
    print("\nParsing done.")

    print("\nStarted Merging sections...")
    merge_section(PARSED_OUTPUT, MERGE_OUTPUT)
    print("\nMerging done.")

    print("\nStarted Persistence in SQL DB...")
    push_records(MERGE_OUTPUT, batch_size=500)
    push_toc(MERGE_OUTPUT, batch_size=500)
    embed_acts(QDRANT_URL)
    print("\nPersistence done.")

    print("\nStarted Chunking...")
    chunker(PARSED_OUTPUT, CHUNKED_OUTPUT)
    print("\nChunking done.")

    print("\nStarted Vector Embedding of chunks...")
    embedder(EMBEDDER_INPUT, QDRANT_URL)
    print("\nEmbedding done.")

    print("\nData Ingestion Done.")


if __name__ == "__main__":
    main()
