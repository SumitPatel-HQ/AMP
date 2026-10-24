"""Selectable fairness planning policy (C-02, ADR-0016)."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mission_plans", sa.Column("planning_policy", sa.String(), nullable=True))
    op.add_column("mission_plans", sa.Column("policy_version", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("mission_plans", "policy_version")
    op.drop_column("mission_plans", "planning_policy")
