from app.db.base import Base
from app.db.session import engine_corpus, engine_main

import app.models_db # here all orm models are imported so that da can create them all when the db start at the beginning later db migrations will not create new tables from scratch but will modify only the changes in the already present tables in database

def init_db():
    Base.metadata.create_all(bind=engine_corpus)
    Base.metadata.create_all(bind=engine_main)
    
def init_db_corpus():
    Base.metadata.create_all(bind=engine_corpus)
    
def init_db_main():
    Base.metadata.create_all(bind=engine_main)

if __name__ == "__main__":
    init_db()