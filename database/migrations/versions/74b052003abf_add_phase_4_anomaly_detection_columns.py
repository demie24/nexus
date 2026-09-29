"""add phase 4 anomaly detection columns

Revision ID: 74b052003abf
Revises: 0c6d6de99a81
Create Date: 2026-09-29 08:24:40.245117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74b052003abf'
down_revision: Union[str, Sequence[str], None] = '0c6d6de99a81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 4 Anomaly Engine fields."""
    op.add_column("anomalies", sa.Column("anomaly_type", sa.String(length=50), server_default="MULTIVARIATE_ANOMALY", nullable=False))
    op.add_column("anomalies", sa.Column("status", sa.String(length=30), server_default="DETECTED", nullable=False))
    op.add_column("anomalies", sa.Column("triggered_signals", sa.JSON(), server_default='[]', nullable=False))
    op.add_column("anomalies", sa.Column("detector_evidence", sa.JSON(), server_default='{}', nullable=False))
    op.add_column("anomalies", sa.Column("explanation", sa.Text(), nullable=True))
    op.add_column("anomalies", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("anomalies", "resolved_at")
    op.drop_column("anomalies", "explanation")
    op.drop_column("anomalies", "detector_evidence")
    op.drop_column("anomalies", "triggered_signals")
    op.drop_column("anomalies", "status")
    op.drop_column("anomalies", "anomaly_type")
