"""add phase 5 predictive intelligence columns

Revision ID: 8b1c4e7f3a92
Revises: 74b052003abf
Create Date: 2026-09-29 08:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b1c4e7f3a92'
down_revision: Union[str, Sequence[str], None] = '74b052003abf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 5 Predictive Intelligence fields."""
    op.add_column("predictions", sa.Column("rul_lower_hours", sa.Float(), nullable=True))
    op.add_column("predictions", sa.Column("rul_upper_hours", sa.Float(), nullable=True))
    op.add_column("predictions", sa.Column("prediction_status", sa.String(length=30), server_default="ESTIMATED", nullable=False))
    op.add_column("predictions", sa.Column("model_version", sa.String(length=50), server_default="v1.0.0", nullable=False))
    op.add_column("predictions", sa.Column("feature_version", sa.String(length=50), server_default="v1.0.0", nullable=False))
    op.add_column("predictions", sa.Column("health_trajectory", sa.JSON(), server_default='{}', nullable=False))
    op.add_column("predictions", sa.Column("risk_forecast", sa.JSON(), server_default='{}', nullable=False))
    op.add_column("predictions", sa.Column("contributing_factors", sa.JSON(), server_default='[]', nullable=False))
    op.add_column("predictions", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("predictions", "created_at")
    op.drop_column("predictions", "contributing_factors")
    op.drop_column("predictions", "risk_forecast")
    op.drop_column("predictions", "health_trajectory")
    op.drop_column("predictions", "feature_version")
    op.drop_column("predictions", "model_version")
    op.drop_column("predictions", "prediction_status")
    op.drop_column("predictions", "rul_upper_hours")
    op.drop_column("predictions", "rul_lower_hours")
