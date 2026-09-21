"""Initial schema: scenarios through experiment results

Mirrors amis/db/schema.py. See that module's docstring for why the
cross-table id columns (event_id, evaluated_plan_id, plan_id on
impacts and decision_traces, parent_plan_id on mission_plans) carry no
foreign key: each of those tables is replaced independently, in its
own transaction, and a constraint there would make an ordinary save
briefly violate referential integrity.

Revision ID: 0001
Revises:
Create Date: 2026-09-21

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("start_time", sa.String, nullable=False),
        sa.Column("end_time", sa.String, nullable=False),
    )

    op.create_table(
        "satellites",
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("id", sa.String, nullable=False),
        sa.Column("battery_capacity_wh", sa.Float, nullable=False),
        sa.Column("battery_charge_wh", sa.Float, nullable=False),
        sa.Column("storage_capacity_mb", sa.Float, nullable=False),
        sa.Column("storage_usage_mb", sa.Float, nullable=False),
        sa.Column("available", sa.Boolean, nullable=False),
    )

    op.create_table(
        "observation_requests",
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("target_lat", sa.Float, nullable=False),
        sa.Column("target_lon", sa.Float, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("duration_s", sa.Float, nullable=False),
        sa.Column("deadline", sa.String, nullable=False),
        sa.Column("energy_cost_wh", sa.Float, nullable=False),
        sa.Column("storage_cost_mb", sa.Float, nullable=False),
        sa.Column("status", sa.String, nullable=False),
    )

    op.create_table(
        "observation_windows",
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("request_id", sa.String, nullable=False),
        sa.Column("satellite_id", sa.String, nullable=False),
        sa.Column("start", sa.String, nullable=False),
        sa.Column("end", sa.String, nullable=False),
        sa.Column("valid", sa.Boolean, nullable=False),
        sa.Column("invalid_reason", sa.String, nullable=True),
    )

    op.create_table(
        "mission_states",
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("simulated_time", sa.String, nullable=False),
        sa.Column("satellite_id", sa.String, nullable=False),
        sa.Column("battery_wh", sa.Float, nullable=False),
        sa.Column("storage_usage_mb", sa.Float, nullable=False),
        sa.Column("available", sa.Boolean, nullable=False),
        sa.Column("active_event_ids", sa.JSON, nullable=False),
        sa.Column("completed_request_ids", sa.JSON, nullable=False),
        sa.Column("mission_complete", sa.Boolean, nullable=False),
    )

    op.create_table(
        "mission_plans",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("parent_plan_id", sa.String, nullable=True),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("mission_utility", sa.Float, nullable=False),
        sa.Column("violation_count", sa.Integer, nullable=False),
        sa.Column("planning_time_ms", sa.Float, nullable=False),
    )
    op.create_index(
        "ix_mission_plans_scenario_id", "mission_plans", ["scenario_id"]
    )

    op.create_table(
        "scheduled_actions",
        sa.Column(
            "plan_id",
            sa.String,
            sa.ForeignKey("mission_plans.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("request_id", sa.String, nullable=False),
        sa.Column("satellite_id", sa.String, nullable=False),
        sa.Column("window_id", sa.String, nullable=False),
        sa.Column("start", sa.String, nullable=False),
        sa.Column("end", sa.String, nullable=False),
        sa.Column("energy_cost_wh", sa.Float, nullable=False),
        sa.Column("storage_cost_mb", sa.Float, nullable=False),
        sa.Column("status", sa.String, nullable=False),
    )

    op.create_table(
        "unscheduled_entries",
        sa.Column(
            "plan_id",
            sa.String,
            sa.ForeignKey("mission_plans.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("request_id", sa.String, primary_key=True),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("reason_code", sa.String, nullable=False),
    )

    op.create_table(
        "mission_events",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("event_time", sa.String, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.create_index(
        "ix_mission_events_scenario_id", "mission_events", ["scenario_id"]
    )

    op.create_table(
        "impacts",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("event_id", sa.String, nullable=False),
        sa.Column("evaluated_plan_id", sa.String, nullable=False),
        sa.Column("frozen_action_ids", sa.JSON, nullable=False),
        sa.Column("valid_unfrozen_action_ids", sa.JSON, nullable=False),
        sa.Column("invalid_unfrozen_action_ids", sa.JSON, nullable=False),
        sa.Column("reason_codes", sa.JSON, nullable=False),
    )
    op.create_index("ix_impacts_scenario_id", "impacts", ["scenario_id"])
    op.create_index("ix_impacts_event_id", "impacts", ["event_id"])
    op.create_index(
        "ix_impacts_evaluated_plan_id", "impacts", ["evaluated_plan_id"]
    )

    op.create_table(
        "decision_traces",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("plan_id", sa.String, nullable=False),
        sa.Column("event_id", sa.String, nullable=True),
        sa.Column("request_id", sa.String, nullable=True),
        sa.Column("reason_code", sa.String, nullable=False),
        sa.Column("previous_action", sa.JSON, nullable=True),
        sa.Column("new_action", sa.JSON, nullable=True),
        sa.Column("constraint_name", sa.String, nullable=True),
        sa.Column("message", sa.String, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False),
    )
    op.create_index(
        "ix_decision_traces_scenario_id", "decision_traces", ["scenario_id"]
    )
    op.create_index("ix_decision_traces_plan_id", "decision_traces", ["plan_id"])

    op.create_table(
        "experiment_results",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.String, nullable=False),
        sa.Column("mission_utility", sa.Float, nullable=False),
        sa.Column("completion_rate", sa.Float, nullable=False),
        sa.Column("violation_count", sa.Integer, nullable=False),
        sa.Column("planning_time_ms", sa.Float, nullable=False),
        sa.Column("battery_utilisation", sa.Float, nullable=False),
        sa.Column("storage_utilisation", sa.Float, nullable=False),
        sa.Column("request_pool_size", sa.Integer, nullable=False),
        sa.Column("request_pool_ids", sa.JSON, nullable=False),
        sa.Column("plan_churn", sa.Float, nullable=True),
        sa.Column("explanation_coverage", sa.Float, nullable=True),
        sa.Column("created_at", sa.String, nullable=False),
    )
    op.create_index(
        "ix_experiment_results_scenario_id", "experiment_results", ["scenario_id"]
    )
    op.create_index(
        "ix_experiment_results_plan_id", "experiment_results", ["plan_id"]
    )


def downgrade() -> None:
    op.drop_table("experiment_results")
    op.drop_table("decision_traces")
    op.drop_table("impacts")
    op.drop_table("mission_events")
    op.drop_table("unscheduled_entries")
    op.drop_table("scheduled_actions")
    op.drop_table("mission_plans")
    op.drop_table("mission_states")
    op.drop_table("observation_windows")
    op.drop_table("observation_requests")
    op.drop_table("satellites")
    op.drop_table("scenarios")
