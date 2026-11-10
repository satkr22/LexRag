from app.common.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

database_url_corpus = settings.DATABASE_URL_CORPUS
database_url_users = settings.DATABASE_URL_USERS

engine_corpus = create_engine(
    url=database_url_corpus,
    echo=False
)

engine_users = create_async_engine(
    url=database_url_users,
    echo=False
)

SessionLocal_corpus = sessionmaker(
    bind=engine_corpus,
    autoflush=False,
    autocommit=False
)

SessionLocal_users = async_sessionmaker(
    bind=engine_users,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)



# fucntion to create one seesion
def get_db_corpus():
    db = SessionLocal_corpus()
    try:
        yield db
    finally:
        db.close()

async def get_db_users():
    db = SessionLocal_users()
    try:
        yield db
    finally:
        await db.close()