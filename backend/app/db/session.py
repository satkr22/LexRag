from app.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

database_url_corpus = settings.DATABASE_URL_CORPUS
database_url_main = settings.DATABASE_URL_MAIN

engine_corpus = create_engine(
    url=database_url_corpus,
    echo=False
)

engine_main = create_engine(
    url=database_url_main,
    echo=False
)

SessionLocal_corpus = sessionmaker(
    bind=engine_corpus,
    autoflush=False,
    autocommit=False
)

SessionLocal_main = sessionmaker(
    bind=engine_main,
    autoflush=False,
    autocommit=False
)



# fucntion to create one seesion
def get_db_corpus():
    db = SessionLocal_corpus()
    try:
        yield db
    finally:
        db.close()

def get_db_main():
    db = SessionLocal_main()
    try:
        yield db
    finally:
        db.close()