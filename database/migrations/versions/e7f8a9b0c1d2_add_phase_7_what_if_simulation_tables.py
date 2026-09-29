"""add phase 7 what if simulation tables and columns

Revision ID: e7f8a9b0c1d2
Revises: 9a2d3e4f5b61
Create Date: 2026-09-29 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = '9a2d3e4f5b61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 7 What-If Counterfactual Simulation tables and columns."""
    # 1. Create simulation_snapshots table
    op.create_table(
        "simulation_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(length=100), nullable=False),
        sa.Column("factory_id", sa.String(length=50), server_default="NEXUS-FACTORY-01", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("machines", sa.JSON(), server_default='[]', nullable=False),
        sa.Column("machine_states", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("telemetry_context", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("prediction_context", sa.JSON(), server_default='{}', nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id")
    )
    op.create_index("ix_simulation_snapshots_snapshot_id", "simulation_snapshots", ["snapshot_id"])

    # 2. Add Phase 7 columns to simulations table
    op.add_column("simulations", sa.Column("simulation_id", sa.String(length=100), nullable=False, server_default="SIM-INIT"))
    op.add_column("simulations", sa.Column("snapshot_id", sa.String(length=100), nullable=False, server_default="SNAP-INIT"))
    op.add_column("simulations", sa.Column("status", sa.String(length=20), server_default="COMPLETED", nullable=False))
    op.add_column("simulations", sa.Column("horizon_hours", sa.Float(), server_default="4.0", nullable=False))
    op.add_column("simulations", sa.Column("parameters", sa.JSON(), server_default='{}', nullable=False))
    op.add_column("simulations", sa.Column("outcome_metrics", sa.JSON(), server_default='{}', nullable=False))
    op.add_column("simulations", sa.Column("baseline_comparison", sa.JSON(), server_default='{}', nullable=False))
    op.add_column("simulations", sa.Column("random_seed", sa.Integer(), nullable=True))
    op.add_column("simulations", sa.Column("state_hash", sa.String(length=64), nullable=True))
    op.add_column("simulations", sa.Column("error_message", sa.Text(), nullable=True))

    op.create_index("ix_simulations_simulation_id", "simulations", ["simulation_id"], unique=True)
    op.create_index("ix_simulations_snapshot_id", "simulations", ["snapshot_id"])
    op.create_index("ix_simulations_target_machine_id", "simulations", ["target_machine_id"])
    op.create_index("ix_simulations_status", "simulations", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_simulations_status", table_name="simulations")
    op.drop_index("ix_simulations_target_machine_id", table_name="simulations")
    op.drop_index("ix_simulations_snapshot_id", table_name="simulations")
    op.drop_index("ix_simulations_simulation_id", table_name="simulations")

    op.drop_column("simulations", "error_message")
    op.drop_column("simulations", "state_hash")
    op.drop_column("simulations", "random_seed")
    op.drop_column("simulations", "baseline_comparison")
    op.drop_column("simulations", "outcome_metrics")
    op.drop_column("simulations", "parameters")
    op.drop_column("simulations", "horizon_hours")
    op.drop_column("simulations", "status")
    op.drop_column("simulations", "snapshot_id")
    op.drop_column("simulations", "simulation_id")

    op.drop_index("ix_simulation_snapshots_snapshot_id", table_name="simulation_snapshots")
    op.drop_table("simulation_snapshots")
