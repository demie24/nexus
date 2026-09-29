"""add phase 6 diagnostics table

Revision ID: 9a2d3e4f5b61
Revises: 8b1c4e7f3a92
Create Date: 2026-09-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a2d3e4f5b61'
down_revision: Union[str, Sequence[str], None] = '8b1c4e7f3a92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 6 Diagnostics (RCA) table."""
    op.create_table(
        "diagnostics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("diagnostic_id", sa.String(length=100), nullable=False),
        sa.Column("machine_id", sa.String(length=50), nullable=False),
        sa.Column("incident_id", sa.String(length=100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("likely_cause", sa.String(length=100), nullable=False),
        sa.Column("evidence_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=20), server_default="LOW", nullable=False),
        sa.Column("ranking", sa.JSON(), server_default='[]', nullable=False),
        sa.Column("evidence_summary", sa.JSON(), server_default='[]', nullable=False),
        sa.Column("text_report", sa.Text(), nullable=False),
        sa.Column("metadata_info", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("provenance", sa.String(length=20), server_default="DIAGNOSED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("diagnostic_id")
    )
    op.create_index("ix_diagnostics_machine_id", "diagnostics", ["machine_id"])
    op.create_index("ix_diagnostics_timestamp", "diagnostics", ["timestamp"])
    op.create_index("ix_diagnostics_incident_id", "diagnostics", ["incident_id"])
    op.create_index("ix_diagnostics_likely_cause", "diagnostics", ["likely_cause"])
    op.create_index("ix_diagnostics_machine_time", "diagnostics", ["machine_id", "timestamp"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_diagnostics_machine_time", table_name="diagnostics")
    op.drop_index("ix_diagnostics_likely_cause", table_name="diagnostics")
    op.drop_index("ix_diagnostics_incident_id", table_name="diagnostics")
    op.drop_index("ix_diagnostics_timestamp", table_name="diagnostics")
    op.drop_index("ix_diagnostics_machine_id", table_name="diagnostics")
    op.drop_table("diagnostics")
