from datetime import datetime
from sqlalchemy import (
    String,
    DateTime
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

    
class TOC(Base):
    
    __tablename__ = "tocs"
    
    
    act: Mapped[str] = mapped_column(
        String(200), 
        nullable=False
    )
    
    # chapter details
    chapter_title: Mapped[str] = mapped_column(
        String, 
        nullable=True
    )
    
    chapter_section_range: Mapped[str] = mapped_column(
        String, 
        nullable=True
    )
    
    # section details
    
    section_number: Mapped[str] = mapped_column(
        String, 
        nullable=False
    )
    
    section_title: Mapped[str] = mapped_column(
        String, 
        nullable=True
    )
    
    # PK
    section_id: Mapped[str] = mapped_column(
        String, 
        primary_key=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    