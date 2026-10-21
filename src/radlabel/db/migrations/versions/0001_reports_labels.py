"""reports and labels (M8)

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("report_id", sa.String(64), primary_key=True),
        sa.Column("findings", sa.Text, nullable=False, server_default=""),
        sa.Column("impression", sa.Text, nullable=False, server_default=""),
        sa.Column("indication", sa.Text, nullable=False, server_default=""),
        sa.Column("comparison", sa.Text, nullable=False, server_default=""),
        sa.Column("sections_identified", sa.Boolean, nullable=False),
    )
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.String(64), sa.ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("verification", sa.String(32), nullable=False),
        sa.Column("evidence", sa.JSON, nullable=False),
        sa.Column("corroboration", sa.String(16), nullable=True),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint("report_id", "label"),
    )
    for col in ("report_id", "label", "status", "verification"):
        op.create_index(f"ix_labels_{col}", "labels", [col])


def downgrade() -> None:
    op.drop_table("labels")
    op.drop_table("reports")
