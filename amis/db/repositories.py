"""SQLAlchemy-backed repositories implementing amis.repositories' protocols.

Each method opens one transaction, reads or writes plain columns and
JSON, and converts at the boundary through the domain type's own
``to_dict``/``from_dict``. No SQLAlchemy row or ORM object crosses out
of this module; every public method returns a domain type from
amis.domain.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from amis.db import schema
from amis.domain import (
    DecisionTrace,
    Impact,
    MissionEvent,
    MissionPlan,
    MissionState,
    ObservationRequest,
    ObservationWindow,
    Satellite,
    Scenario,
)
from amis.errors import (
    InvalidScenarioError,
    PlanVersionConflictError,
    ResourceNotFoundError,
)
from amis.repositories import Repositories


def _without(mapping: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key not in keys}


class SqlScenarioRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, scenario: Scenario) -> None:
        # The scenarios.id primary key is the source of truth for
        # uniqueness, not a check-then-insert, so two concurrent
        # requests creating the same scenario id can never both
        # succeed the way a SELECT-then-INSERT race would allow.
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    insert(schema.scenarios).values(
                        **_without(scenario.to_dict(), "satellite", "requests")
                    )
                )
                conn.execute(
                    insert(schema.satellites).values(
                        scenario_id=scenario.id, **scenario.satellite.to_dict()
                    )
                )
                if scenario.requests:
                    conn.execute(
                        insert(schema.observation_requests),
                        [
                            {
                                "scenario_id": scenario.id,
                                "seq": seq,
                                **request.to_dict(),
                            }
                            for seq, request in enumerate(scenario.requests)
                        ],
                    )
        except IntegrityError as error:
            raise InvalidScenarioError(
                "a scenario with that id already exists",
                details={"scenario_id": scenario.id},
            ) from error

    def get(self, scenario_id: str) -> Scenario:
        with self._engine.begin() as conn:
            scenario_row = (
                conn.execute(
                    select(schema.scenarios).where(
                        schema.scenarios.c.id == scenario_id
                    )
                )
                .mappings()
                .first()
            )
            if scenario_row is None:
                raise ResourceNotFoundError(
                    "scenario does not exist", details={"scenario_id": scenario_id}
                )
            satellite_row = (
                conn.execute(
                    select(schema.satellites).where(
                        schema.satellites.c.scenario_id == scenario_id
                    )
                )
                .mappings()
                .one()
            )
            request_rows = (
                conn.execute(
                    select(schema.observation_requests)
                    .where(schema.observation_requests.c.scenario_id == scenario_id)
                    .order_by(schema.observation_requests.c.seq)
                )
                .mappings()
                .all()
            )
        satellite = Satellite.from_dict(
            _without(dict(satellite_row), "scenario_id")
        )
        requests = tuple(
            ObservationRequest.from_dict(_without(dict(row), "scenario_id", "seq"))
            for row in request_rows
        )
        return Scenario(
            id=scenario_row["id"],
            name=scenario_row["name"],
            start_time=datetime.fromisoformat(scenario_row["start_time"]),
            end_time=datetime.fromisoformat(scenario_row["end_time"]),
            satellite=satellite,
            requests=requests,
        )


class SqlObservationWindowRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def replace_for_scenario(
        self, scenario_id: str, windows: tuple[ObservationWindow, ...]
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                delete(schema.observation_windows).where(
                    schema.observation_windows.c.scenario_id == scenario_id
                )
            )
            if windows:
                conn.execute(
                    insert(schema.observation_windows),
                    [
                        {"scenario_id": scenario_id, "seq": seq, **window.to_dict()}
                        for seq, window in enumerate(windows)
                    ],
                )

    def list_for_scenario(self, scenario_id: str) -> tuple[ObservationWindow, ...]:
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    select(schema.observation_windows)
                    .where(schema.observation_windows.c.scenario_id == scenario_id)
                    .order_by(schema.observation_windows.c.seq)
                )
                .mappings()
                .all()
            )
        return tuple(
            ObservationWindow.from_dict(_without(dict(row), "scenario_id", "seq"))
            for row in rows
        )


class SqlPlanRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def replace_for_scenario(
        self,
        scenario_id: str,
        plans: tuple[MissionPlan, ...],
        *,
        expected_current_plan_id: str | None = None,
    ) -> None:
        with self._engine.begin() as conn:
            current_row = (
                conn.execute(
                    select(schema.mission_plans.c.id)
                    .where(schema.mission_plans.c.scenario_id == scenario_id)
                    .order_by(schema.mission_plans.c.version.desc())
                    .limit(1)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            current_id = current_row["id"] if current_row is not None else None
            if (
                expected_current_plan_id is not None
                and current_id != expected_current_plan_id
            ):
                raise PlanVersionConflictError(
                    "replan named a plan version that is no longer current",
                    details={
                        "expected_parent_plan_id": expected_current_plan_id,
                        "current_plan_id": current_id,
                    },
                )

            # SQLite does not enforce ON DELETE CASCADE unless a pragma
            # is set per connection, so a plan's own scheduled_actions
            # and unscheduled_entries are deleted explicitly here rather
            # than relied on to cascade from deleting mission_plans.
            existing_plan_ids = [
                row["id"]
                for row in conn.execute(
                    select(schema.mission_plans.c.id).where(
                        schema.mission_plans.c.scenario_id == scenario_id
                    )
                )
                .mappings()
                .all()
            ]
            conn.execute(
                delete(schema.scheduled_actions).where(
                    schema.scheduled_actions.c.plan_id.in_(existing_plan_ids)
                )
            )
            conn.execute(
                delete(schema.unscheduled_entries).where(
                    schema.unscheduled_entries.c.plan_id.in_(existing_plan_ids)
                )
            )
            conn.execute(
                delete(schema.mission_plans).where(
                    schema.mission_plans.c.scenario_id == scenario_id
                )
            )

            for plan in plans:
                conn.execute(
                    insert(schema.mission_plans).values(
                        **_without(plan.to_dict(), "actions", "unscheduled")
                    )
                )
                if plan.actions:
                    conn.execute(
                        insert(schema.scheduled_actions),
                        [
                            {"plan_id": plan.id, "seq": seq, **action.to_dict()}
                            for seq, action in enumerate(plan.actions)
                        ],
                    )
                if plan.unscheduled:
                    conn.execute(
                        insert(schema.unscheduled_entries),
                        [
                            {"plan_id": plan.id, "seq": seq, **entry.to_dict()}
                            for seq, entry in enumerate(plan.unscheduled)
                        ],
                    )

    def list_for_scenario(self, scenario_id: str) -> tuple[MissionPlan, ...]:
        with self._engine.begin() as conn:
            plan_rows = (
                conn.execute(
                    select(schema.mission_plans)
                    .where(schema.mission_plans.c.scenario_id == scenario_id)
                    .order_by(schema.mission_plans.c.version)
                )
                .mappings()
                .all()
            )
            return tuple(self._load_plan(conn, dict(row)) for row in plan_rows)

    def get(self, plan_id: str) -> MissionPlan:
        with self._engine.begin() as conn:
            plan_row = (
                conn.execute(
                    select(schema.mission_plans).where(
                        schema.mission_plans.c.id == plan_id
                    )
                )
                .mappings()
                .first()
            )
            if plan_row is None:
                raise ResourceNotFoundError(
                    "plan does not exist", details={"plan_id": plan_id}
                )
            return self._load_plan(conn, dict(plan_row))

    def _load_plan(self, conn: Connection, plan_row: dict[str, Any]) -> MissionPlan:
        action_rows = (
            conn.execute(
                select(schema.scheduled_actions)
                .where(schema.scheduled_actions.c.plan_id == plan_row["id"])
                .order_by(schema.scheduled_actions.c.seq)
            )
            .mappings()
            .all()
        )
        unscheduled_rows = (
            conn.execute(
                select(schema.unscheduled_entries)
                .where(schema.unscheduled_entries.c.plan_id == plan_row["id"])
                .order_by(schema.unscheduled_entries.c.seq)
            )
            .mappings()
            .all()
        )
        return MissionPlan.from_dict(
            {
                **plan_row,
                "actions": [
                    _without(dict(row), "plan_id", "seq") for row in action_rows
                ],
                "unscheduled": [
                    _without(dict(row), "plan_id", "seq") for row in unscheduled_rows
                ],
            }
        )


class SqlEventRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def replace_for_scenario(
        self, scenario_id: str, events: tuple[MissionEvent, ...]
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                delete(schema.mission_events).where(
                    schema.mission_events.c.scenario_id == scenario_id
                )
            )
            if events:
                conn.execute(
                    insert(schema.mission_events),
                    [
                        {"seq": seq, **event.to_dict()}
                        for seq, event in enumerate(events)
                    ],
                )

    def list_for_scenario(self, scenario_id: str) -> tuple[MissionEvent, ...]:
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    select(schema.mission_events)
                    .where(schema.mission_events.c.scenario_id == scenario_id)
                    .order_by(schema.mission_events.c.seq)
                )
                .mappings()
                .all()
            )
        return tuple(
            MissionEvent.from_dict(_without(dict(row), "seq")) for row in rows
        )


class SqlImpactRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def replace_for_scenario(
        self, scenario_id: str, impacts: tuple[Impact, ...]
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                delete(schema.impacts).where(
                    schema.impacts.c.scenario_id == scenario_id
                )
            )
            if impacts:
                conn.execute(
                    insert(schema.impacts),
                    [
                        {"scenario_id": scenario_id, "seq": seq, **impact.to_dict()}
                        for seq, impact in enumerate(impacts)
                    ],
                )

    def list_for_scenario(self, scenario_id: str) -> tuple[Impact, ...]:
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    select(schema.impacts)
                    .where(schema.impacts.c.scenario_id == scenario_id)
                    .order_by(schema.impacts.c.seq)
                )
                .mappings()
                .all()
            )
        return tuple(
            Impact.from_dict(_without(dict(row), "scenario_id", "seq"))
            for row in rows
        )


class SqlTraceRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def replace_for_scenario(
        self, scenario_id: str, traces: tuple[DecisionTrace, ...]
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                delete(schema.decision_traces).where(
                    schema.decision_traces.c.scenario_id == scenario_id
                )
            )
            if traces:
                conn.execute(
                    insert(schema.decision_traces),
                    [
                        {"scenario_id": scenario_id, "seq": seq, **trace.to_dict()}
                        for seq, trace in enumerate(traces)
                    ],
                )

    def list_for_scenario(self, scenario_id: str) -> tuple[DecisionTrace, ...]:
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    select(schema.decision_traces)
                    .where(schema.decision_traces.c.scenario_id == scenario_id)
                    .order_by(schema.decision_traces.c.seq)
                )
                .mappings()
                .all()
            )
        return tuple(
            DecisionTrace.from_dict(_without(dict(row), "scenario_id", "seq"))
            for row in rows
        )


class SqlMissionStateRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def put(self, state: MissionState) -> None:
        # Try the insert first and fall back to an update on a primary
        # key conflict, rather than checking existence first: a
        # SELECT-then-decide race would let two concurrent puts both
        # see "no row yet" and both attempt to insert.
        try:
            with self._engine.begin() as conn:
                conn.execute(insert(schema.mission_states).values(**state.to_dict()))
        except IntegrityError:
            with self._engine.begin() as conn:
                conn.execute(
                    update(schema.mission_states)
                    .where(schema.mission_states.c.scenario_id == state.scenario_id)
                    .values(**_without(state.to_dict(), "scenario_id"))
                )

    def get(self, scenario_id: str) -> MissionState:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    select(schema.mission_states).where(
                        schema.mission_states.c.scenario_id == scenario_id
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise ResourceNotFoundError(
                "mission state does not exist", details={"scenario_id": scenario_id}
            )
        return MissionState.from_dict(dict(row))


def build_repositories(engine: Engine) -> Repositories:
    """Wire the SQLAlchemy-backed repositories behind the same protocols.

    Tables must already exist (run the Alembic migrations first); this
    factory never creates or alters schema.
    """

    return Repositories(
        scenarios=SqlScenarioRepository(engine),
        windows=SqlObservationWindowRepository(engine),
        plans=SqlPlanRepository(engine),
        events=SqlEventRepository(engine),
        impacts=SqlImpactRepository(engine),
        traces=SqlTraceRepository(engine),
        states=SqlMissionStateRepository(engine),
    )
