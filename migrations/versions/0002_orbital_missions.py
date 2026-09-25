"""Stored orbit, policy, target names and window geometry.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scenarios", sa.Column("window_policy", sa.JSON(), nullable=True))
    op.add_column("scenarios", sa.Column("created_at", sa.String(), nullable=True))
    op.add_column("satellites", sa.Column("orbit", sa.JSON(), nullable=True))
    op.add_column("observation_requests", sa.Column("target_name", sa.String(), nullable=True))
    for name, column_type in (
        ("peak_elevation_deg", sa.Float()), ("peak_time", sa.String()),
        ("min_off_nadir_deg", sa.Float()), ("sun_elevation_deg", sa.Float()),
        ("source", sa.String()),
    ):
        op.add_column("observation_windows", sa.Column(name, column_type, nullable=True))

    # Pre-3fe5208 databases were stamped 0001 with id-only keys. That
    # revision was later edited in place. Repair the old PostgreSQL keys here.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        inspector = sa.inspect(bind)
        for table in ("mission_events", "impacts", "decision_traces"):
            pk = inspector.get_pk_constraint(table)
            if pk["constrained_columns"] == ["id"]:
                op.drop_constraint(pk["name"], table, type_="primary")
                op.create_primary_key(f"pk_{table}_scenario_id", table, ["scenario_id", "id"])


def downgrade() -> None:
    for name in ("peak_elevation_deg", "peak_time", "min_off_nadir_deg", "sun_elevation_deg", "source"):
        op.drop_column("observation_windows", name)
    op.drop_column("observation_requests", "target_name")
    op.drop_column("satellites", "orbit")
    op.drop_column("scenarios", "window_policy")
    op.drop_column("scenarios", "created_at")
