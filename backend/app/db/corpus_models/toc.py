from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    DateTime, 
    Index
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
        String(200), 
        nullable=True
    )
    
    chapter_start_section: Mapped[str] = mapped_column(
        String(100), 
        nullable=True
    )
    chapter_end_section: Mapped[str] = mapped_column(
        String(100), 
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
    
    section_order: Mapped[int] = mapped_column(
        Integer,
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
        Index("idx_tocs_act_chapter_range", "act", "chapter_start_section", "chapter_end_section"),
        Index("idx_tocs_act_order", "act", "section_order"),
    )
    