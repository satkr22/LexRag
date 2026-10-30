from pathlib import Path

from backend.app.rag.data_ingestion.web_scrapper.scrap import main as scrapper 
from backend.app.rag.data_ingestion.parser.parse_html import main as parser 
from backend.app.rag.data_ingestion.parser.merge_sections import merge_section
from backend.app.rag.data_ingestion.chunker.chunk import process_corpus as chunker
from backend.app.rag.vector_embeddings.h_embedder_gpu import main as embedder
from backend.app.rag.data_ingestion.persist_sections import push_records
from backend.app.rag.data_ingestion.persist_tocs import push_toc

SCRAPPED_OUTPUT = Path(__file__).parent / "data_ingestion" / "scrapped"

PARSED_OUTPUT = Path(__file__).parent / "data_ingestion" / "parsed"
MERGE_OUTPUT = Path(__file__).parent / "data_ingestion" / "parsed" / "aaalll"

CHUNKED_OUTPUT = Path(__file__).parent / "data_ingestion" / "chunked"

EMBEDDER_INPUT = Path(__file__).parent / "data_ingestion" / "chunked" / "aaalll"
VECTOR_DB_PATH = Path(__file__).parents[3] / "qdrant_db"


def main():
    print("\nStarted Scrapping from web...")
    scrapper(SCRAPPED_OUTPUT)
    print("\nScrapping done.")
    
    print("\nStarted Parsing scrapped html...")
    parser(SCRAPPED_OUTPUT, PARSED_OUTPUT)
    print("\nParsing done.")
    
    print("\nStarted Merging sections...")
    merge_section(PARSED_OUTPUT, MERGE_OUTPUT)
    print("\nMerging done.")
    
    print("\nStarted Sections Persistence in SQL DB...")
    push_records(MERGE_OUTPUT, batch_size=500)
    push_toc(MERGE_OUTPUT, batch_size=500)
    print("\nPersistence done.")
    
    print("\nStarted Chunking...")
    chunker(PARSED_OUTPUT, CHUNKED_OUTPUT)
    print("\nChunking done.")
    
    print("\nStarted Vector Embedding od chunks...")
    embedder(EMBEDDER_INPUT, VECTOR_DB_PATH)
    print("\nEmbedding done.")
    
    print("\n\nData Ingestion Done.")
    
    

if __name__ == "__main__":
    main()
    
    
    