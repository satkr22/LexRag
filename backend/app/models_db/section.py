from app.db.base import Base
from datetime import datetime
from sqlalchemy import (
    Text,
    String,
    DateTime
)
from sqlalchemy.orm import Mapped, mapped_column


    
class Section(Base):
    
    __tablename__ = "sections"
    
    
    act: Mapped[str] = mapped_column(
        String(200), 
        nullable=False
    )
    
    # section details
    # PK
    section_id: Mapped[str] = mapped_column(
        String, 
        primary_key=True
    )
    
    section_content: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    
    section_number: Mapped[str] = mapped_column(
        String, 
        nullable=False
    )
    
    section_title: Mapped[str] = mapped_column(
        String, 
        nullable=True
    )
    
    # chapter details
    chapter_number: Mapped[str] = mapped_column(
        String, 
        nullable=True
    )
    
    chapter_title: Mapped[str] = mapped_column(
        String, 
        nullable=True
    )
    
    chapter_section_range: Mapped[str] = mapped_column(
        String, 
        nullable=True
    )
    
    # act category details
    category_id: Mapped[str] = mapped_column(
            String, 
            nullable=False
        )
        
    category_code: Mapped[str] = mapped_column(
        String, 
        nullable=False
    )
        
    category_label: Mapped[str] = mapped_column(
        String, 
        nullable=False
    )
    
    # doc title [hint: 'act' is doc code]
    document_title: Mapped[str] = mapped_column(
        String, 
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    