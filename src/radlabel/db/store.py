"""Write pipeline outputs to Postgres (SPEC §6.3). Input: PipelineResult only (report text as parsed + predicted
labels); nothing else reaches the tables."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Engine, create_engine, delete
from sqlalchemy.orm import Session

from radlabel.config import get_settings
from radlabel.db.models import Label, Report
from radlabel.pipeline import PipelineResult


def engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    return create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))


def rows(r: PipelineResult) -> tuple[Report, list[Label]]:
    p = r.parse
    rep = Report(report_id=r.report_id, findings=p.findings, impression=p.impression, indication=p.indication,
                 comparison=p.comparison, sections_identified=r.sections_identified)
    labs = [Label(report_id=r.report_id, label=f.label, status=f.status, verification=f.verification,
                  evidence=f.evidence, corroboration=f.corroboration, reason=f.reason) for f in r.final]
    return rep, labs


def store(eng: Engine, results: Iterable[PipelineResult]) -> int:
    """Replace each report's rows (idempotent reruns). Returns the number of reports written."""
    n = 0
    with Session(eng) as s, s.begin():
        for r in results:
            s.execute(delete(Label).where(Label.report_id == r.report_id))
            s.execute(delete(Report).where(Report.report_id == r.report_id))
            rep, labs = rows(r)
            s.add(rep)
            s.flush()  # the report row first: labels reference it (no ORM relationship orders the inserts)
            s.add_all(labs)
            n += 1
    return n
