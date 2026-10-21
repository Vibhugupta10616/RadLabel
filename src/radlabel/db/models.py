"""Postgres schema (README §5, §6.3, M8). Created by Alembic (`alembic upgrade head`), never ad hoc.

- `reports`: unchanged report sections as parsed; the indication is a separate column (Q&A only, never indexed).
- `labels`: PREDICTED v2 labels only (status, verification state, evidence, corroboration, reason). No codes from
  the dataset, folds or eval data anywhere (tests/test_index_leakage.py).
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Report(Base):
    __tablename__ = "reports"
    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    findings: Mapped[str] = mapped_column(Text, default="")
    impression: Mapped[str] = mapped_column(Text, default="")
    indication: Mapped[str] = mapped_column(Text, default="")
    comparison: Mapped[str] = mapped_column(Text, default="")
    sections_identified: Mapped[bool] = mapped_column(Boolean)


class Label(Base):
    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("report_id", "label"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.report_id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    verification: Mapped[str] = mapped_column(String(32), index=True)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    corroboration: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
