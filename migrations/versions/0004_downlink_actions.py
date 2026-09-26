"""Downlink actions: action kind, station id, request-less rows (ADR-0011)."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("scheduled_actions")}
    with op.batch_alter_table("scheduled_actions") as batch:
        if "kind" not in columns:
            batch.add_column(sa.Column("kind", sa.String(), nullable=False, server_default="imaging"))
        if "station_id" not in columns:
            batch.add_column(sa.Column("station_id", sa.String(), nullable=True))
        batch.alter_column("request_id", existing_type=sa.String(), nullable=True)
        batch.alter_column("window_id", existing_type=sa.String(), nullable=True)


def downgrade():
    op.execute("DELETE FROM scheduled_actions WHERE kind = 'downlink'")
    with op.batch_alter_table("scheduled_actions") as batch:
        batch.alter_column("window_id", existing_type=sa.String(), nullable=False)
        batch.alter_column("request_id", existing_type=sa.String(), nullable=False)
        batch.drop_column("station_id")
        batch.drop_column("kind")
