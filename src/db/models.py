from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional
from pgvector.sqlalchemy import Vector

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ARRAY, JSON
from src.db.base import Base


class RegulationPart(Base):
    __tablename__ = "regulation_parts"
    __table_args__ = (
        UniqueConstraint(
            "title_number",
            "part_number",
            "version_date",
            name="uq_regulation_parts_title_part_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    part_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    version_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    heading: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sections: Mapped[list["RegulationSection"]] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
    )


class RegulationSection(Base):
    __tablename__ = "regulation_sections"
    __table_args__ = (
        UniqueConstraint(
            "part_id",
            "section_number",
            name="uq_regulation_sections_part_id_section_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("regulation_parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_section_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    version_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    part: Mapped["RegulationPart"] = relationship(back_populates="sections")


class Change(Base):
    __tablename__ = "changes"
    __table_args__ = (
        UniqueConstraint(
            "document_short_code",
            "section_number",
            "old_date",
            "new_date",
            name="uq_change_section_dates",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_short_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    section_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    old_part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("regulation_parts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    new_part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("regulation_parts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    old_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    new_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    raw_diff: Mapped[str] = mapped_column(Text, nullable=False)

    change_type: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    classification_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class ImpactAnalysis(Base):
    __tablename__ = "impact_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    change_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("changes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    what_changed: Mapped[str] = mapped_column(Text, nullable=False)
    affected_functions: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    affected_processes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    action_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    citations: Mapped[Optional[list[dict]]] = mapped_column(JSON, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class ContextDocument(Base):
    __tablename__ = "context_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    corpus: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    document_short_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    publication_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class ContextChunk(Base):
    __tablename__ = "context_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("context_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

__table_args__ = (
    UniqueConstraint("document_id", "chunk_index", name="uq_context_chunks_document_chunk_index"),
)