from enum import Enum
from uuid import uuid4
from datetime import datetime

from sqlalchemy import (
    Text,
    String,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class Role(str, Enum):
    USER = "user"
    AGENT = "agent"
    
class Chat_Message(Base):
    
    __tablename__ = "chat_messages"
    
    # PK
    message_id: Mapped[str] = mapped_column(
        String, 
        primary_key=True,
        default=lambda: str(uuid4())
    )
    
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False
    )
    
    user_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )
    
    role: Mapped[Role] = mapped_column(
        SQLEnum(Role, name="role"), 
        nullable=False
    )
    
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    