"""Repository protocols and request-independent in-memory implementations."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Generic, Protocol, TypeVar

from amis.domain import (
    DecisionTrace,
    Impact,
    MissionEvent,
    MissionPlan,
    MissionState,
    ObservationWindow,
    PlanDiff,
    Scenario,
)
from amis.errors import (
    InvalidScenarioError,
    PlanVersionConflictError,
    ResourceNotFoundError,
)
from amis.planning import Planner
from amis.session import MissionSession
from amis.windows import WindowProvider


class ScenarioRepository(Protocol):
    def add(self, scenario: Scenario) -> None: ...

    def get(self, scenario_id: str) -> Scenario: ...


class ObservationWindowRepository(Protocol):
    def replace_for_scenario(
        self,
        scenario_id: str,
        windows: tuple[ObservationWindow, ...],
        *,
        connection: Any | None = None,
    ) -> None: ...

    def list_for_scenario(self, scenario_id: str) -> tuple[ObservationWindow, ...]: ...


class PlanRepository(Protocol):
    def replace_for_scenario(
        self,
        scenario_id: str,
        plans: tuple[MissionPlan, ...],
        *,
        expected_current_plan_id: str | None = None,
        connection: Any | None = None,
    ) -> None: ...

    def list_for_scenario(self, scenario_id: str) -> tuple[MissionPlan, ...]: ...

    def get(self, plan_id: str) -> MissionPlan: ...


class EventRepository(Protocol):
    def replace_for_scenario(
        self,
        scenario_id: str,
        events: tuple[MissionEvent, ...],
        *,
        connection: Any | None = None,
    ) -> None: ...

    def list_for_scenario(self, scenario_id: str) -> tuple[MissionEvent, ...]: ...


class ImpactRepository(Protocol):
    def replace_for_scenario(
        self,
        scenario_id: str,
        impacts: tuple[Impact, ...],
        *,
        connection: Any | None = None,
    ) -> None: ...

    def list_for_scenario(self, scenario_id: str) -> tuple[Impact, ...]: ...


class TraceRepository(Protocol):
    def replace_for_scenario(
        self,
        scenario_id: str,
        traces: tuple[DecisionTrace, ...],
        *,
        connection: Any | None = None,
    ) -> None: ...

    def list_for_scenario(self, scenario_id: str) -> tuple[DecisionTrace, ...]: ...


class MissionStateRepository(Protocol):
    def put(self, state: MissionState, *, connection: Any | None = None) -> None: ...

    def get(self, scenario_id: str) -> MissionState: ...


class InMemoryScenarioRepository:
    def __init__(self) -> None:
        self._items: dict[str, Scenario] = {}
        self._lock = RLock()

    def add(self, scenario: Scenario) -> None:
        with self._lock:
            if scenario.id in self._items:
                raise InvalidScenarioError(
                    "a scenario with that id already exists",
                    details={"scenario_id": scenario.id},
                )
            self._items[scenario.id] = scenario

    def get(self, scenario_id: str) -> Scenario:
        with self._lock:
            scenario = self._items.get(scenario_id)
        if scenario is None:
            raise ResourceNotFoundError(
                "scenario does not exist", details={"scenario_id": scenario_id}
            )
        return scenario


class InMemoryPlanRepository:
    def __init__(self) -> None:
        self._items: dict[str, tuple[MissionPlan, ...]] = {}
        self._lock = RLock()

    def replace_for_scenario(
        self,
        scenario_id: str,
        plans: tuple[MissionPlan, ...],
        *,
        expected_current_plan_id: str | None = None,
        connection: Any | None = None,
    ) -> None:
        del connection  # in-memory writes are already atomic under the lock
        with self._lock:
            current = self._items.get(scenario_id, ())
            current_id = current[-1].id if current else None
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
            self._items[scenario_id] = plans

    def list_for_scenario(self, scenario_id: str) -> tuple[MissionPlan, ...]:
        with self._lock:
            return self._items.get(scenario_id, ())

    def get(self, plan_id: str) -> MissionPlan:
        with self._lock:
            matches = [
                plan
                for plans in self._items.values()
                for plan in plans
                if plan.id == plan_id
            ]
        if len(matches) != 1:
            raise ResourceNotFoundError(
                "plan does not exist", details={"plan_id": plan_id}
            )
        return matches[0]


RecordT = TypeVar("RecordT")


class InMemoryScenarioListRepository(Generic[RecordT]):
    def __init__(self) -> None:
        self._items: dict[str, tuple[RecordT, ...]] = {}
        self._lock = RLock()

    def replace_for_scenario(
        self,
        scenario_id: str,
        records: tuple[RecordT, ...],
        *,
        connection: Any | None = None,
    ) -> None:
        del connection  # in-memory writes are already atomic under the lock
        with self._lock:
            self._items[scenario_id] = records

    def list_for_scenario(self, scenario_id: str) -> tuple[RecordT, ...]:
        with self._lock:
            return self._items.get(scenario_id, ())


class InMemoryMissionStateRepository:
    def __init__(self) -> None:
        self._items: dict[str, MissionState] = {}
        self._lock = RLock()

    def put(self, state: MissionState, *, connection: Any | None = None) -> None:
        del connection  # in-memory writes are already atomic under the lock
        with self._lock:
            self._items[state.scenario_id] = state

    def get(self, scenario_id: str) -> MissionState:
        with self._lock:
            state = self._items.get(scenario_id)
        if state is None:
            raise ResourceNotFoundError(
                "mission state does not exist", details={"scenario_id": scenario_id}
            )
        return state


@dataclass(frozen=True)
class Repositories:
    scenarios: ScenarioRepository
    windows: ObservationWindowRepository
    plans: PlanRepository
    events: EventRepository
    impacts: ImpactRepository
    traces: TraceRepository
    states: MissionStateRepository
    # Set only for SQL-backed repositories (see amis/db/repositories.py's
    # build_repositories). When present, MissionSessionStore.save() opens
    # one transaction on it and threads the connection through every
    # write, so a save is committed or rejected as a unit (GAP-06). The
    # in-memory repositories need no such thing: their writes are already
    # atomic under their own locks.
    engine: Any | None = None

    @staticmethod
    def in_memory() -> "Repositories":
        return Repositories(
            scenarios=InMemoryScenarioRepository(),
            windows=InMemoryScenarioListRepository[ObservationWindow](),
            plans=InMemoryPlanRepository(),
            events=InMemoryScenarioListRepository[MissionEvent](),
            impacts=InMemoryScenarioListRepository[Impact](),
            traces=InMemoryScenarioListRepository[DecisionTrace](),
            states=InMemoryMissionStateRepository(),
        )


class MissionSessionStore:
    """Rehydrate and persist one request-scoped MissionSession."""

    def __init__(
        self,
        repositories: Repositories,
        *,
        window_provider: WindowProvider | None = None,
        planner: Planner | None = None,
    ) -> None:
        self.repositories = repositories
        self.window_provider = window_provider
        self.planner = planner

    def create(self, scenario: Scenario) -> MissionSession:
        session = self._new_session(scenario.id)
        session.load_scenario(scenario)
        self.repositories.scenarios.add(scenario)
        self.save(session)
        return session

    def load(self, scenario_id: str) -> MissionSession:
        scenario = self.repositories.scenarios.get(scenario_id)
        session = self._new_session(scenario.id)
        session.restore(
            scenario,
            windows=self.repositories.windows.list_for_scenario(scenario_id),
            plans=self.repositories.plans.list_for_scenario(scenario_id),
            state=self.repositories.states.get(scenario_id),
            events=self.repositories.events.list_for_scenario(scenario_id),
            impacts=self.repositories.impacts.list_for_scenario(scenario_id),
            traces=self.repositories.traces.list_for_scenario(scenario_id),
        )
        return session

    def load_for_plan(self, plan_id: str) -> tuple[MissionSession, MissionPlan]:
        plan = self.repositories.plans.get(plan_id)
        return self.load(plan.scenario_id), plan

    def compare_plans(self, old_plan_id: str, new_plan_id: str) -> PlanDiff:
        old_plan = self.repositories.plans.get(old_plan_id)
        new_plan = self.repositories.plans.get(new_plan_id)
        if new_plan.scenario_id != old_plan.scenario_id:
            raise ResourceNotFoundError(
                "plans do not belong to the same scenario",
                details={
                    "old_plan_id": old_plan_id,
                    "new_plan_id": new_plan_id,
                },
            )
        session = self.load(old_plan.scenario_id)
        return session.compare_versions(old_plan.version, new_plan.version)

    def save(
        self,
        session: MissionSession,
        *,
        expected_current_plan_id: str | None = None,
    ) -> None:
        scenario_id = session.get_scenario().id
        if self.repositories.engine is None:
            self._write(scenario_id, session, expected_current_plan_id, connection=None)
            return
        # One transaction for every table this save touches, so a failure
        # partway through leaves nothing committed rather than an
        # invalidated window with no event to explain it (GAP-06).
        with self.repositories.engine.begin() as connection:
            self._write(scenario_id, session, expected_current_plan_id, connection=connection)

    def _write(
        self,
        scenario_id: str,
        session: MissionSession,
        expected_current_plan_id: str | None,
        *,
        connection: Any | None,
    ) -> None:
        self.repositories.plans.replace_for_scenario(
            scenario_id,
            session.get_plans(),
            expected_current_plan_id=expected_current_plan_id,
            connection=connection,
        )
        self.repositories.windows.replace_for_scenario(
            scenario_id, session.get_windows(), connection=connection
        )
        self.repositories.events.replace_for_scenario(
            scenario_id, session.get_events(), connection=connection
        )
        self.repositories.impacts.replace_for_scenario(
            scenario_id, session.get_impacts(), connection=connection
        )
        self.repositories.traces.replace_for_scenario(
            scenario_id, session.get_traces(), connection=connection
        )
        self.repositories.states.put(session.get_state(), connection=connection)

    def _new_session(self, scenario_id: str) -> MissionSession:
        return MissionSession(
            window_provider=self.window_provider,
            planner=self.planner,
            plan_id_prefix=f"{scenario_id}:PLAN",
        )
