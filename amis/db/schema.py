"""SQLAlchemy Core table definitions for AMIS persistence.

Column names deliberately mirror the keys each domain type's ``to_dict``
emits (see amis/domain/*.py), so a repository can write a row with
``**entity.to_dict()`` and read one back with ``Entity.from_dict(row)``.
Timestamps are stored as the same ISO-8601 strings ``to_dict`` already
produces rather than a dialect-specific datetime column, so a plan, an
event, or a trace round-trips identically on SQLite (in tests) and on
PostgreSQL (in Docker Compose).

Foreign keys are declared only where a table's rows are always replaced
in the same transaction as the parent they reference: a scenario's own
satellite and requests, and a plan's own actions and unscheduled
entries. Impacts, decision traces, and mission events reference a plan
or an event id, but ``EventRepository`` and ``PlanRepository`` each
replace their whole table for a scenario independently, in their own
transaction. A cross-table foreign key there would make every ordinary
save briefly violate referential integrity, so those columns are plain,
indexed strings instead. See docs/adr/0006.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
)

metadata = MetaData()

scenarios = Table(
    "scenarios",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("start_time", String, nullable=False),
    Column("end_time", String, nullable=False),
)

satellites = Table(
    "satellites",
    metadata,
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("id", String, nullable=False),
    Column("battery_capacity_wh", Float, nullable=False),
    Column("battery_charge_wh", Float, nullable=False),
    Column("storage_capacity_mb", Float, nullable=False),
    Column("storage_usage_mb", Float, nullable=False),
    Column("available", Boolean, nullable=False),
)

observation_requests = Table(
    "observation_requests",
    metadata,
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("id", String, primary_key=True),
    Column("seq", Integer, nullable=False),
    Column("target_lat", Float, nullable=False),
    Column("target_lon", Float, nullable=False),
    Column("priority", Integer, nullable=False),
    Column("duration_s", Float, nullable=False),
    Column("deadline", String, nullable=False),
    Column("energy_cost_wh", Float, nullable=False),
    Column("storage_cost_mb", Float, nullable=False),
    Column("status", String, nullable=False),
)

observation_windows = Table(
    "observation_windows",
    metadata,
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("id", String, primary_key=True),
    Column("seq", Integer, nullable=False),
    Column("request_id", String, nullable=False),
    Column("satellite_id", String, nullable=False),
    Column("start", String, nullable=False),
    Column("end", String, nullable=False),
    Column("valid", Boolean, nullable=False),
    Column("invalid_reason", String, nullable=True),
)

mission_states = Table(
    "mission_states",
    metadata,
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("simulated_time", String, nullable=False),
    Column("satellite_id", String, nullable=False),
    Column("battery_wh", Float, nullable=False),
    Column("storage_usage_mb", Float, nullable=False),
    Column("available", Boolean, nullable=False),
    Column("active_event_ids", JSON, nullable=False),
    Column("completed_request_ids", JSON, nullable=False),
    Column("mission_complete", Boolean, nullable=False),
)

mission_plans = Table(
    "mission_plans",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("version", Integer, nullable=False),
    Column("parent_plan_id", String, nullable=True),
    Column("created_at", String, nullable=False),
    Column("mission_utility", Float, nullable=False),
    Column("violation_count", Integer, nullable=False),
    Column("planning_time_ms", Float, nullable=False),
)

scheduled_actions = Table(
    "scheduled_actions",
    metadata,
    Column(
        "plan_id",
        String,
        ForeignKey("mission_plans.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("id", String, primary_key=True),
    Column("seq", Integer, nullable=False),
    Column("request_id", String, nullable=False),
    Column("satellite_id", String, nullable=False),
    Column("window_id", String, nullable=False),
    Column("start", String, nullable=False),
    Column("end", String, nullable=False),
    Column("energy_cost_wh", Float, nullable=False),
    Column("storage_cost_mb", Float, nullable=False),
    Column("status", String, nullable=False),
)

unscheduled_entries = Table(
    "unscheduled_entries",
    metadata,
    Column(
        "plan_id",
        String,
        ForeignKey("mission_plans.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("request_id", String, primary_key=True),
    Column("seq", Integer, nullable=False),
    Column("reason_code", String, nullable=False),
)

mission_events = Table(
    "mission_events",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("seq", Integer, nullable=False),
    Column("event_type", String, nullable=False),
    Column("event_time", String, nullable=False),
    Column("payload", JSON, nullable=False),
)

impacts = Table(
    "impacts",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("seq", Integer, nullable=False),
    Column("event_id", String, nullable=False, index=True),
    Column("evaluated_plan_id", String, nullable=False, index=True),
    Column("frozen_action_ids", JSON, nullable=False),
    Column("valid_unfrozen_action_ids", JSON, nullable=False),
    Column("invalid_unfrozen_action_ids", JSON, nullable=False),
    Column("reason_codes", JSON, nullable=False),
)

decision_traces = Table(
    "decision_traces",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("seq", Integer, nullable=False),
    Column("plan_id", String, nullable=False, index=True),
    Column("event_id", String, nullable=True),
    Column("request_id", String, nullable=True),
    Column("reason_code", String, nullable=False),
    Column("previous_action", JSON, nullable=True),
    Column("new_action", JSON, nullable=True),
    Column("constraint_name", String, nullable=True),
    Column("message", String, nullable=False),
    Column("metadata", JSON, nullable=False),
)

# Recommended by AMIS_SRD.md section 19 for the experiment browser cut
# from the MVP sprint. No repository writes here yet: MetricsResult is
# computed on demand from the tables above and nothing above the
# repository boundary calls back in to store it. The table exists now
# so that landing it later is a repository change, not a migration.
experiment_results = Table(
    "experiment_results",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "scenario_id",
        String,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("plan_id", String, nullable=False, index=True),
    Column("mission_utility", Float, nullable=False),
    Column("completion_rate", Float, nullable=False),
    Column("violation_count", Integer, nullable=False),
    Column("planning_time_ms", Float, nullable=False),
    Column("battery_utilisation", Float, nullable=False),
    Column("storage_utilisation", Float, nullable=False),
    Column("request_pool_size", Integer, nullable=False),
    Column("request_pool_ids", JSON, nullable=False),
    Column("plan_churn", Float, nullable=True),
    Column("explanation_coverage", Float, nullable=True),
    Column("created_at", String, nullable=False),
)
