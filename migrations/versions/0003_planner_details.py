"""Persist per-run planner and solver evidence."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("mission_plans")}
    for name, kind in (("planner_name", sa.String()), ("solver_details", sa.JSON())):
        if name not in columns:
            op.add_column("mission_plans", sa.Column(name, kind, nullable=True))


def downgrade():
    op.drop_column("mission_plans", "solver_details")
    op.drop_column("mission_plans", "planner_name")
