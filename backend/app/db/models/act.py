# app/models/act.py
from datetime import datetime
from sqlalchemy import String, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Act(Base):
    __tablename__ = "acts"

    act_code: Mapped[str] = mapped_column(String(64), primary_key=True)

    act_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # CRITICAL
    # NOTE: execute the below commands in psql manually after creation of acts table or using alembic migrations
    '''
        1. Enable the extension (once per database)
        CREATE EXTENSION IF NOT EXISTS pg_trgm;

        2. Trigram index on lower(act_name)
        CREATE INDEX IF NOT EXISTS idx_acts_act_name_trgm
        ON acts
        USING gin (lower(act_name) gin_trgm_ops);

        3. Trigram index on lower(act_code)
        CREATE INDEX IF NOT EXISTS idx_acts_act_code_trgm
        ON acts
        USING gin (lower(act_code) gin_trgm_ops);
        
    '''

    def __repr__(self) -> str:
        return f"<Act code={self.act_code!r} name={self.act_name!r}>"