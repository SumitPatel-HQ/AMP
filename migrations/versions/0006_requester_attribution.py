"""Optional explicit requester attribution (C-01, ADR-0016)."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("observation_requests", sa.Column("requester_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("observation_requests", "requester_id")
