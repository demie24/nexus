"""add phase 8 decisions table

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-29 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 8 Decisions table."""
    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(length=100), nullable=False),
        sa.Column("machine_id", sa.String(length=50), nullable=False),
        sa.Column("snapshot_id", sa.String(length=100), nullable=False),
        sa.Column("policy_profile", sa.String(length=50), nullable=False),
        sa.Column("criteria_weights", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("constraints", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("candidate_actions", sa.JSON(), server_default='[]', nullable=False),
        sa.Column("decision_scores", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("feasibility", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("rank_stability", sa.String(length=50), server_default="HIGH_STABILITY", nullable=False),
        sa.Column("confidence", sa.String(length=20), server_default="HIGH", nullable=False),
        sa.Column("evidence_references", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("decision_explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="COMPLETED", nullable=False),
        sa.Column("provenance", sa.String(length=20), server_default="RECOMMENDED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id")
    )
    op.create_index("ix_decisions_decision_id", "decisions", ["decision_id"], unique=True)
    op.create_index("ix_decisions_machine_id", "decisions", ["machine_id"])
    op.create_index("ix_decisions_snapshot_id", "decisions", ["snapshot_id"])
    op.create_index("ix_decisions_created_at", "decisions", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_decisions_created_at", table_name="decisions")
    op.drop_index("ix_decisions_snapshot_id", table_name="decisions")
    op.drop_index("ix_decisions_machine_id", table_name="decisions")
    op.drop_index("ix_decisions_decision_id", table_name="decisions")
    op.drop_table("decisions")
