"""Multiple satellites per mission (Wave 7, ADR-0014).

``satellites`` becomes a per-scenario list, keyed like
``observation_requests`` (scenario_id, id, seq). ``mission_states``
drops its single-satellite scalar columns for one JSON ``satellites``
column holding each satellite's battery, storage, availability, and
completed-request set; ``observation_requests`` gains a nullable
``satellite_id`` for a request that names its satellite.
"""

import json

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    satellite_columns = {c["name"] for c in inspector.get_columns("satellites")}
    if "seq" not in satellite_columns:
        op.add_column("satellites", sa.Column("seq", sa.Integer(), nullable=True))
    op.execute("UPDATE satellites SET seq = 0 WHERE seq IS NULL")
    with op.batch_alter_table("satellites", recreate="always") as batch:
        batch.alter_column("seq", existing_type=sa.Integer(), nullable=False, server_default="0")
        batch.create_primary_key("pk_satellites", ["scenario_id", "id"])

    request_columns = {c["name"] for c in inspector.get_columns("observation_requests")}
    if "satellite_id" not in request_columns:
        op.add_column("observation_requests", sa.Column("satellite_id", sa.String(), nullable=True))

    state_columns = {c["name"] for c in inspector.get_columns("mission_states")}
    if "satellites" not in state_columns:
        op.add_column("mission_states", sa.Column("satellites", sa.JSON(), nullable=True))
        rows = bind.execute(sa.text(
            "SELECT scenario_id, satellite_id, battery_wh, storage_usage_mb, available, "
            "completed_request_ids FROM mission_states"
        )).mappings().all()
        for row in rows:
            payload = [{
                "satellite_id": row["satellite_id"],
                "battery_wh": row["battery_wh"],
                "storage_usage_mb": row["storage_usage_mb"],
                "available": bool(row["available"]),
                "completed_request_ids": (
                    row["completed_request_ids"]
                    if isinstance(row["completed_request_ids"], list)
                    else json.loads(row["completed_request_ids"] or "[]")
                ),
            }]
            bind.execute(
                sa.text("UPDATE mission_states SET satellites = :satellites WHERE scenario_id = :scenario_id"),
                {"satellites": json.dumps(payload), "scenario_id": row["scenario_id"]},
            )
        with op.batch_alter_table("mission_states", recreate="always") as batch:
            batch.alter_column("satellites", existing_type=sa.JSON(), nullable=False)
            batch.drop_column("satellite_id")
            batch.drop_column("battery_wh")
            batch.drop_column("storage_usage_mb")
            batch.drop_column("available")
            batch.drop_column("completed_request_ids")


def downgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("mission_states", recreate="always") as batch:
        batch.add_column(sa.Column("satellite_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("battery_wh", sa.Float(), nullable=True))
        batch.add_column(sa.Column("storage_usage_mb", sa.Float(), nullable=True))
        batch.add_column(sa.Column("available", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("completed_request_ids", sa.JSON(), nullable=True))
    rows = bind.execute(sa.text("SELECT scenario_id, satellites FROM mission_states")).mappings().all()
    for row in rows:
        satellites = row["satellites"] if isinstance(row["satellites"], list) else json.loads(row["satellites"])
        first = satellites[0]
        bind.execute(
            sa.text(
                "UPDATE mission_states SET satellite_id = :satellite_id, battery_wh = :battery_wh, "
                "storage_usage_mb = :storage_usage_mb, available = :available, "
                "completed_request_ids = :completed_request_ids WHERE scenario_id = :scenario_id"
            ),
            {
                "satellite_id": first["satellite_id"],
                "battery_wh": first["battery_wh"],
                "storage_usage_mb": first["storage_usage_mb"],
                "available": first["available"],
                "completed_request_ids": json.dumps(first["completed_request_ids"]),
                "scenario_id": row["scenario_id"],
            },
        )
    with op.batch_alter_table("mission_states", recreate="always") as batch:
        batch.alter_column("satellite_id", existing_type=sa.String(), nullable=False)
        batch.alter_column("battery_wh", existing_type=sa.Float(), nullable=False)
        batch.alter_column("storage_usage_mb", existing_type=sa.Float(), nullable=False)
        batch.alter_column("available", existing_type=sa.Boolean(), nullable=False)
        batch.alter_column("completed_request_ids", existing_type=sa.JSON(), nullable=False)
        batch.drop_column("satellites")

    op.drop_column("observation_requests", "satellite_id")

    # Downgrade keeps only the first satellite per scenario (Wave 7's
    # multi-satellite rows have nowhere to go in the single-satellite shape).
    op.execute(
        "DELETE FROM satellites WHERE (scenario_id, seq) NOT IN "
        "(SELECT scenario_id, MIN(seq) FROM satellites GROUP BY scenario_id)"
    )
    with op.batch_alter_table("satellites", recreate="always") as batch:
        batch.create_primary_key("pk_satellites", ["scenario_id"])
        batch.drop_column("seq")
