from app.db.base import Base
from datetime import datetime
from sqlalchemy import (
    Text,
    String,
    DateTime,
    Index
)
from sqlalchemy.orm import Mapped, mapped_column


    
class Chat_Session(Base):
    
    __tablename__ = "chat_sessions"
    
    # PK
    session_id: Mapped[str] = mapped_column(
        String, 
        primary_key=True
    )
    
    user_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )
    
    title: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    __table_args__ = (
        Index("idx_chat_sessions_user_id", "user_id"),
    )
    
    