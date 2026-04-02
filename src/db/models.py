from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class RegulationPart(Base):
    __tablename__ = "regulation_parts"

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    part: Mapped["RegulationPart"] = relationship(back_populates="sections")