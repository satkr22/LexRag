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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UserBase

class Role(str, Enum):
    USER = "user"
    AGENT = "agent"
    
class User_Meta(UserBase):
    
    __tablename__ = "users_meta"
    
    # PK
    user_id: Mapped[str] = mapped_column(
        String, 
        primary_key=True,
    )
    
    username: Mapped[str] = mapped_column(
        String,
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    