"""Deterministic optional-interval planner under the one-way resource model.

Wave 6 (ADR-0013): slew is a sequence-dependent setup time. Every pair of
actions on one satellite gets an order literal, and the pair's own slew
gap is enforced in whichever order the solver picks. With sunlight
recharge the battery is a chain of lower-bound levels over short time
buckets (`_add_recharge_battery_budget`), sound under the capacity cap.

Downlink (ADR-0011): reservations do not depend on the imaging choice, so
their storage releases are known before the solve. With any release the
storage is a chain of upper-bound levels between releases
(`_add_downlink_storage_budget`), matching the floored timeline walk.

Wave 7 (ADR-0014): every no-overlap group and every resource budget is
scoped to one satellite. A window already names the satellite it was
computed against, so "at most one window chosen" (summed across every
candidate window of a request, on any of its candidate satellites)
is exactly the assignment rule: a request lands on at most one
satellite, decided by the objective rather than a separate assignment
stage.

Ticket C-02 (ADR-0016): opt-in `utility_then_fairness` policy. Solves in
deterministic stages: Stage 1 proves maximum primary utility; Stage 2
minimizes the requester utility gap at that fixed proven utility;
Stage 3 optimizes stability preference. Causality between pre-fairness
and final solutions derives REBALANCED_FOR_REQUESTER_SHARE.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from fractions import Fraction
from itertools import combinations
from typing import Any, Iterable, NamedTuple

from ortools.sat.python import cp_model
import ortools

from amis.constraints import (ResourceProjection, check_deadline, check_overlap,
    check_satellite_availability, check_window_containment, validate_plan)
from amis.domain import (ActionStatus, ContactWindow, imaging_actions, MissionPlan, MissionState, ObservationRequest,
    ObservationWindow, ReasonCode, RequestStatus, Satellite, Scenario, ScheduledAction, UnscheduledEntry)
from amis.dynamics.recharge import RechargeModel, recharge_model
from amis.dynamics.slew import SlewModel
from amis.ids import ACTION_ID_PREFIX, FIRST_PLAN_ID, format_id
from amis.planning.downlink import finalize_downlinks, reserve_downlinks
from amis.planning.greedy import (GreedyPlanner, _frozen_actions, _ordered_candidates,
    _candidate_starts_in_window, _unscheduled_reason)

_BUCKET_S = 600
_SOLVED = (cp_model.OPTIMAL, cp_model.FEASIBLE)


def _candidate_satellites(scenario: Scenario, request: ObservationRequest) -> list[Satellite]:
    if request.satellite_id is not None:
        return [scenario.satellite_by_id(request.satellite_id)]
    return sorted(scenario.satellites, key=lambda item: item.id)


class _Candidate(NamedTuple):
    """One optional (request, window) placement in the model."""

    request: ObservationRequest
    window: ObservationWindow
    present: Any
    start: Any


@dataclass(frozen=True)
class _Item:
    """One action on one satellite, frozen or optional.

    ``present`` is ``True`` for a frozen action, else its presence literal.
    ``start`` is an int for a frozen action, else its start variable;
    ``low``/``high`` bound it, in seconds from the scenario start. ``cost``
    carries the resource costs when the action still has to be paid for
    (a frozen PLANNED action or a candidate request), else ``None``.
    """

    request_id: str
    present: Any
    start: Any
    duration: int
    low: int
    high: int
    cost: ObservationRequest | ScheduledAction | None

    @property
    def fixed(self) -> bool:
        return self.present is True


def _add_pairwise_slew(model: cp_model.CpModel, items: list[_Item], slew: SlewModel) -> None:
    """Order each pair of actions and enforce that pair's own slew gap.

    Pairs of the same request are exclusive, and two frozen actions are
    already placed, so both are skipped. A pair with no gap is left to the
    no-overlap constraint.
    """
    for j, k in combinations(range(len(items)), 2):
        first, second = items[j], items[k]
        if first.request_id == second.request_id or (first.fixed and second.fixed):
            continue
        gap = math.ceil(slew.gap_s(first.request_id, second.request_id))
        if gap == 0:
            continue
        both = [item.present for item in (first, second) if not item.fixed]
        before = model.new_bool_var(f"order_{j}_{k}")
        model.add(second.start >= first.start + first.duration + gap).only_enforce_if([*both, before])
        model.add(first.start >= second.start + second.duration + gap).only_enforce_if([*both, before.Not()])


def _scale(values: list[Fraction]) -> int:
    """Common denominator: exact decimal ratios avoid rounding a resource
    budget into overcommitment."""
    scale = math.lcm(*(value.denominator for value in values))
    if sum(abs(value) for value in values) * scale >= 2**62:
        raise ValueError("Resource precision exceeds CP-SAT integer range")
    return scale


def _add_linear_budget(model: cp_model.CpModel, items: list[_Item], attr: str, available: float) -> None:
    """Everything paid must fit what is available now: the one-way budget."""
    paid = [item for item in items if item.cost is not None]
    costs = [Fraction(str(getattr(item.cost, attr))) for item in paid]
    budget = Fraction(str(available)) - sum(cost for item, cost in zip(paid, costs) if item.fixed)
    scale = _scale([budget, *costs])
    optional = [(item, int(cost * scale)) for item, cost in zip(paid, costs) if not item.fixed]
    bound = math.floor(budget * scale)
    model.add(sum(cost * item.present for item, cost in optional) <= max(0, bound))
    if bound < 0:
        for item, _ in optional:
            model.add(item.present == 0)


def _landings(model: cp_model.CpModel, items: list[_Item], buckets: list[tuple[int, int]]) -> list[list[tuple[int, Any]]]:
    """Per bucket, ``(item index, literal)`` for each item that may start in it.

    A frozen item lands with the literal ``True``. An optional item whose
    start range fits one bucket reuses its presence literal; otherwise it
    gets one literal per bucket, exactly one of them true when present.
    """
    landings: list[list[tuple[int, Any]]] = [[] for _ in buckets]
    for index, item in enumerate(items):
        spans = [number for number, (low, high) in enumerate(buckets) if low <= item.high and item.low < high]
        if item.fixed or len(spans) == 1:
            landings[spans[0]].append((index, item.present))
            continue
        inside_literals = []
        for number in spans:
            inside = model.new_bool_var("")
            low, high = buckets[number]
            model.add(item.start >= low).only_enforce_if(inside)
            model.add(item.start < high).only_enforce_if(inside)
            landings[number].append((index, inside))
            inside_literals.append(inside)
        model.add(sum(inside_literals) == item.present)
    return landings


def _bucket_spend(scaled: list[int], landed: list[tuple[int, Any]]) -> Any:
    return sum(scaled[index] * (1 if literal is True else literal) for index, literal in landed)


def _candidate_literals(landed: list[tuple[int, Any]]) -> list[Any]:
    """The landings a bucket check applies to: frozen actions are exempt
    (ADR-0003), so a bucket only has to fit when a candidate lands in it."""
    return [literal for _, literal in landed if literal is not True]


def _buckets(edges: set[int]) -> list[tuple[int, int]]:
    ordered = sorted(edges)
    return list(zip(ordered, ordered[1:]))


def _add_recharge_battery_budget(model: cp_model.CpModel, items: list[_Item], recharge: RechargeModel,
                                 initial_wh: float, capacity_wh: float,
                                 simulated_time: datetime, origin: datetime) -> None:
    """Battery as a chain of lower-bound levels over short time buckets.

    Buckets end at every sunlit edge and at least every ``_BUCKET_S``
    seconds. ``level[b]`` is a lower bound on the battery when bucket ``b``
    opens. Everything spent in a bucket must fit its opening level, so no
    in-bucket gain is ever credited before a spend. The capped walk ends
    the bucket with at least ``min(level + gain, C) - spend``, so the next
    level is bounded by both ``level + gain - spend`` and ``C - spend``.
    Gain and capacity are floored, so rounding never overstates the
    battery. A frozen deficit carries forward, blocking later candidates
    until recharge repays it.
    """
    paid = [item for item in items if item.cost is not None]
    if not paid:
        return
    costs = [Fraction(str(item.cost.energy_cost_wh)) for item in paid]
    initial = Fraction(str(initial_wh))
    capacity = Fraction(str(capacity_wh)) if math.isfinite(capacity_wh) else None
    scale = _scale([initial, *costs, *([capacity] if capacity is not None else [])])
    scaled = [int(cost * scale) for cost in costs]

    seconds = lambda instant: (instant - origin).total_seconds()
    opening = math.floor(seconds(simulated_time))
    closing = max(item.high for item in paid) + 1
    edges = {opening, closing, *range(opening, closing, _BUCKET_S)}
    for lit_start, lit_end in recharge.sunlit:
        edges.update(edge for edge in (math.ceil(seconds(lit_start)), math.floor(seconds(lit_end)))
                     if opening < edge < closing)
    buckets = _buckets(edges)
    gains = [math.floor(Fraction(recharge.gain_wh(max(simulated_time, origin + timedelta(seconds=low)),
                                                   origin + timedelta(seconds=high))) * scale)
             for low, high in buckets]
    landings = _landings(model, paid, buckets)

    ceiling = math.floor(initial * scale) + sum(gains)
    if capacity is not None:
        ceiling = max(math.floor(initial * scale), min(ceiling, math.floor(capacity * scale)))
    level = model.new_constant(math.floor(initial * scale))
    for number, landed in enumerate(landings):
        spend = _bucket_spend(scaled, landed)
        for literal in _candidate_literals(landed):
            model.add(spend <= level).only_enforce_if(literal)
        following = model.new_int_var(-sum(scaled), ceiling, f"battery_{number}")
        model.add(following <= level + gains[number] - spend)
        if capacity is not None:
            model.add(following <= math.floor(capacity * scale) - spend)
        level = following


def _add_downlink_storage_budget(model: cp_model.CpModel, items: list[_Item], releases: list[ScheduledAction],
                                 used_mb: float, capacity_mb: float,
                                 simulated_time: datetime, origin: datetime) -> None:
    """Storage as a chain of upper-bound levels between downlink releases.

    A release lands at its contact's end, and the walk applies it before an
    imaging charge at the same instant (ADR-0011), so each release closes a
    bucket at the first whole second at or after that end. Charges inside a
    bucket must all fit on top of its opening level, since no release lands
    inside a bucket. The walk floors storage at zero, so the next level is
    at least ``max(0, level + charge - release)``. Releases are floored and
    nothing else is rounded, so the chain never understates storage.
    """
    paid = [item for item in items if item.cost is not None]
    if not paid:
        return
    costs = [Fraction(str(item.cost.storage_cost_mb)) for item in paid]
    initial = Fraction(str(used_mb))
    capacity = Fraction(str(capacity_mb))
    scale = _scale([initial, capacity, *costs])
    scaled = [int(cost * scale) for cost in costs]

    seconds = lambda instant: (instant - origin).total_seconds()
    opening = math.floor(seconds(simulated_time))
    closing = max(item.high for item in paid) + 1
    released: dict[int, int] = {}
    for release in releases:
        edge = math.ceil(seconds(release.end))
        if opening < edge < closing:
            released[edge] = released.get(edge, 0) + math.floor(-Fraction(str(release.storage_cost_mb)) * scale)
    buckets = _buckets({opening, closing, *released})
    landings = _landings(model, paid, buckets)

    ceiling = math.floor(initial * scale) + sum(scaled)
    level = model.new_constant(math.floor(initial * scale))
    for number, landed in enumerate(landings):
        charge = _bucket_spend(scaled, landed)
        for literal in _candidate_literals(landed):
            model.add(level + charge <= math.floor(capacity * scale)).only_enforce_if(literal)
        following = model.new_int_var(0, ceiling, f"storage_{number}")
        model.add(following >= level + charge - released.get(buckets[number][1], 0))
        level = following


class _ModelBuilder:
    """The CP-SAT model for one planning call: placements, then constraints."""

    def __init__(self, scenario: Scenario, mission_state: MissionState) -> None:
        self.model = cp_model.CpModel()
        self.scenario = scenario
        self.state = mission_state
        self.origin = scenario.start_time
        self.satellites = sorted(scenario.satellites, key=lambda item: item.id)
        self.intervals: dict[str, list] = {satellite.id: [] for satellite in self.satellites}
        self.items: dict[str, list[_Item]] = {satellite.id: [] for satellite in self.satellites}
        self.candidates: list[_Candidate] = []
        self.penalties: list[Any] = []
        self.penalty_ranges: list[int] = []
        self._outage_count = 0

    def seconds(self, instant: datetime) -> float:
        return (instant - self.origin).total_seconds()

    def add_frozen(self, frozen: Iterable[ScheduledAction]) -> None:
        for action in imaging_actions(frozen):
            fixed_start = math.floor(self.seconds(action.start))
            fixed_duration = math.ceil(self.seconds(action.end)) - fixed_start
            self.intervals[action.satellite_id].append(
                self.model.new_fixed_size_interval_var(fixed_start, fixed_duration, f"frozen_{action.id}"))
            self.items[action.satellite_id].append(_Item(
                action.request_id, True, fixed_start, fixed_duration, fixed_start, fixed_start,
                action if action.status is ActionStatus.PLANNED else None))

    def add_request(self, request: ObservationRequest, windows: Iterable[ObservationWindow],
                    outages: tuple[tuple[str, datetime, datetime], ...], culmination: bool) -> None:
        candidate_ids = {satellite.id for satellite in _candidate_satellites(self.scenario, request)}
        literals = []
        for window in windows:
            if (
                window.request_id != request.id
                or window.satellite_id not in candidate_ids
                or not window.valid
                or not self.state.for_satellite(window.satellite_id).available
            ):
                continue
            duration = math.ceil(request.duration_s)
            low = math.ceil(self.seconds(max(window.start, self.state.simulated_time, self.origin)))
            high = math.floor(self.seconds(min(window.end, request.deadline, self.scenario.end_time))) - duration
            if high < low:
                continue
            present = self.model.new_bool_var(f"present_{window.id}")
            start = self.model.new_int_var(low, high, f"start_{window.id}")
            self.intervals[window.satellite_id].append(
                self.model.new_optional_fixed_size_interval_var(start, duration, present, window.id))
            literals.append(present)
            self.candidates.append(_Candidate(request, window, present, start))
            self.items[window.satellite_id].append(_Item(request.id, present, start, duration, low, high, request))
            for outage_satellite_id, outage_start, outage_end in outages:
                if outage_satellite_id == window.satellite_id:
                    self._avoid_outage(present, start, duration, low, high, outage_start, outage_end)
            if culmination and window.peak_time is not None:
                self._prefer_culmination(request, window, present, start, low, high)
        # At most one (satellite, window) chosen across every candidate:
        # the assignment decision falls out of this same constraint.
        self.model.add(sum(literals) <= 1)

    def _avoid_outage(self, present, start, duration: int, low: int, high: int,
                      outage_start: datetime, outage_end: datetime) -> None:
        opens = math.ceil(self.seconds(outage_start))
        closes = math.ceil(self.seconds(outage_end))
        if closes < low or opens - duration > high:
            return
        before = self.model.new_bool_var(f"outage_before_{self._outage_count}")
        after = self.model.new_bool_var(f"outage_after_{self._outage_count}")
        self._outage_count += 1
        self.model.add(start + duration <= opens).only_enforce_if(before)
        self.model.add(start + duration > opens).only_enforce_if(before.Not())
        self.model.add(start >= closes).only_enforce_if(after)
        self.model.add(start < closes).only_enforce_if(after.Not())
        self.model.add_bool_or([before, after]).only_enforce_if(present)

    def _prefer_culmination(self, request: ObservationRequest, window: ObservationWindow,
                            present, start, low: int, high: int) -> None:
        centered = int(round(self.seconds(window.peak_time - timedelta(seconds=request.duration_s / 2))))
        target = min(high, max(low, centered))
        penalty = self.model.new_int_var(0, high - low, f"culm_{window.id}")
        self.model.add(penalty >= start - target).only_enforce_if(present)
        self.model.add(penalty >= target - start).only_enforce_if(present)
        self.penalties.append(penalty)
        self.penalty_ranges.append(high - low)

    def add_satellite_constraints(self, satellite: Satellite, slew: SlewModel,
                                  releases: list[ScheduledAction]) -> None:
        items = self.items[satellite.id]
        self.model.add_no_overlap(self.intervals[satellite.id])
        _add_pairwise_slew(self.model, items, slew)
        satellite_state = self.state.for_satellite(satellite.id)
        if releases:
            _add_downlink_storage_budget(self.model, items, releases, satellite_state.storage_usage_mb,
                                         satellite.storage_capacity_mb, self.state.simulated_time, self.origin)
        else:
            _add_linear_budget(self.model, items, "storage_cost_mb",
                               satellite.storage_capacity_mb - satellite_state.storage_usage_mb)
        recharge = recharge_model(self.scenario, satellite)
        if recharge.recharge_rate_w > 0:
            _add_recharge_battery_budget(self.model, items, recharge, satellite_state.battery_wh,
                                         satellite.battery_capacity_wh, self.state.simulated_time, self.origin)
        else:
            _add_linear_budget(self.model, items, "energy_cost_wh", satellite_state.battery_wh)

    def maximize_utility(self, previous: dict[str, ScheduledAction], weight: int) -> None:
        priority_terms = [
            (c.request.priority * weight
             + int(c.request.id in previous and previous[c.request.id].window_id == c.window.id)) * c.present
            for c in self.candidates
        ]
        if self.penalties:
            # Geometry tie-break only: scale priority above any possible
            # total culmination distance so the preference never displaces
            # a higher-utility selection.
            scale = sum(self.penalty_ranges) + 1
            self.model.maximize(sum(term * scale for term in priority_terms) - sum(self.penalties))
        else:
            self.model.maximize(sum(priority_terms))


class CpSatPlanner:
    def __init__(self, deterministic_limit: float = 1.0, policy: str = "utility") -> None:
        if not math.isfinite(deterministic_limit) or deterministic_limit <= 0:
            raise ValueError("deterministic_limit must be positive and finite")
        if policy not in ("utility", "utility_then_fairness"):
            raise ValueError(f"Unknown planning policy: '{policy}'")
        self.deterministic_limit = deterministic_limit
        self.policy = policy

    def plan(self, scenario: Scenario, mission_state: MissionState,
             requests: Iterable[ObservationRequest], windows: Iterable[ObservationWindow],
             previous_plan: MissionPlan | None = None, plan_id: str = FIRST_PLAN_ID,
             first_action_number: int = 1,
             outage_intervals: Iterable[tuple[str, datetime, datetime]] = (),
             contacts: Iterable[ContactWindow] = ()) -> MissionPlan:
        started = time.perf_counter()
        requests = tuple(sorted(requests, key=lambda r: r.id))
        windows = tuple(sorted(windows, key=lambda w: (w.request_id, w.start, w.id)))
        outages = tuple(outage_intervals)
        contacts = tuple(contacts)
        slew_by_satellite = {
            satellite.id: SlewModel.from_scenario(scenario, satellite, requests) for satellite in scenario.satellites
        }
        culmination = bool(scenario.window_policy and scenario.window_policy.culmination_placement)
        baseline = GreedyPlanner().plan(scenario, mission_state, requests, windows,
                                       previous_plan, plan_id, first_action_number, outages, contacts)
        frozen = _frozen_actions(previous_plan, mission_state)
        frozen_ids = {a.request_id for a in imaging_actions(frozen)}
        eligible = [r for r in requests if r.id not in frozen_ids
                    and r.status not in (RequestStatus.COMPLETED, RequestStatus.EXPIRED)]
        previous = {a.request_id: a for a in imaging_actions(previous_plan.actions)} if previous_plan else {}
        reservations = reserve_downlinks(scenario, mission_state, contacts, frozen)
        releases = [*reservations,
                    *(a for a in frozen if a.is_downlink and a.status is ActionStatus.PLANNED)]

        builder = _ModelBuilder(scenario, mission_state)
        builder.add_frozen(frozen)
        for request in eligible:
            builder.add_request(request, windows, outages, culmination)
        for satellite in builder.satellites:
            builder.add_satellite_constraints(satellite, slew_by_satellite[satellite.id],
                                              [r for r in releases if r.satellite_id == satellite.id])
        weight = len(eligible) + 1

        identified_requesters = sorted({r.requester_id for r in requests if r.requester_id is not None})

        if self.policy == "utility":
            return self._plan_utility(
                scenario, mission_state, requests, eligible, windows, frozen, reservations,
                previous, builder, baseline, slew_by_satellite, outages, weight,
                first_action_number, started, plan_id, contacts
            )

        # policy == "utility_then_fairness"
        if len(identified_requesters) < 2:
            return self._plan_fairness_skipped_fewer_requesters(
                scenario, mission_state, requests, eligible, windows, frozen, reservations,
                previous, builder, baseline, slew_by_satellite, outages, weight,
                first_action_number, started, plan_id, identified_requesters, contacts
            )

        return self._plan_staged_fairness(
            scenario, mission_state, requests, eligible, windows, frozen, reservations,
            previous, builder, baseline, slew_by_satellite, outages, weight,
            first_action_number, started, plan_id, identified_requesters, contacts
        )

    def _plan_utility(
        self, scenario, mission_state, requests, eligible, windows, frozen, reservations,
        previous, builder, baseline, slew_by_satellite, outages, weight,
        first_action_number, started, plan_id, contacts=()
    ) -> MissionPlan:
        builder.maximize_utility(previous, weight)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 0
        solver.parameters.max_deterministic_time = self.deterministic_limit
        status = solver.solve(builder.model)
        if status == cp_model.MODEL_INVALID:
            raise ValueError(f"Invalid CP-SAT model: {builder.model.validate()}")
        imaging = self._selected_actions(solver, status, builder, first_action_number)
        utility = sum(r.priority for r in requests if r.id in {a.request_id for a in [*frozen, *imaging]})
        use_baseline = status not in _SOLVED or utility < baseline.mission_utility
        if use_baseline:
            actions = list(baseline.actions)
            utility = baseline.mission_utility
            fallback_reason = "utility_below_baseline" if status in _SOLVED else "solver_infeasible"
        else:
            actions = list(frozen) + self._with_downlinks(scenario, mission_state, reservations, frozen,
                                                          imaging, first_action_number)
            fallback_reason = None
        unscheduled = self._explain(eligible, windows, actions, mission_state, scenario, previous, outages, slew_by_satellite)
        details = self._solver_details(
            solver, status, use_baseline, weight,
            policy="utility",
            fallback_reason=fallback_reason,
            skip_reason=None,
            fairness_population=None,
            budget_allocation={"utility": self.deterministic_limit},
            achieved_gap=None,
            stability_result=None,
            stages=[{
                "stage": "utility",
                "status": solver.status_name(status),
                "objective": solver.objective_value if status in _SOLVED else None,
                "objective_bound": solver.best_objective_bound if status in _SOLVED else None,
                "objective_unit": "priority_utility",
                "budget": self.deterministic_limit,
            }],
            rebalanced_ids=(),
        )
        result = replace(baseline, actions=tuple(actions), unscheduled=tuple(unscheduled),
            mission_utility=utility, planner_name="cp_sat", planning_policy="utility",
            policy_version="requester-utility-v1", solver_details=details,
            planning_time_ms=(time.perf_counter() - started) * 1000)
        return replace(result, violation_count=len(validate_plan(scenario, mission_state, requests, windows, result, outages, contacts)))

    def _plan_fairness_skipped_fewer_requesters(
        self, scenario, mission_state, requests, eligible, windows, frozen, reservations,
        previous, builder, baseline, slew_by_satellite, outages, weight,
        first_action_number, started, plan_id, identified_requesters, contacts=()
    ) -> MissionPlan:
        builder.maximize_utility(previous, weight)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 0
        solver.parameters.max_deterministic_time = self.deterministic_limit
        status = solver.solve(builder.model)
        if status == cp_model.MODEL_INVALID:
            raise ValueError(f"Invalid CP-SAT model: {builder.model.validate()}")
        imaging = self._selected_actions(solver, status, builder, first_action_number)
        utility = sum(r.priority for r in requests if r.id in {a.request_id for a in [*frozen, *imaging]})
        use_baseline = status not in _SOLVED or utility < baseline.mission_utility
        if use_baseline:
            actions = list(baseline.actions)
            utility = baseline.mission_utility
            fallback_reason = "utility_below_baseline" if status in _SOLVED else "solver_infeasible"
        else:
            actions = list(frozen) + self._with_downlinks(scenario, mission_state, reservations, frozen,
                                                          imaging, first_action_number)
            fallback_reason = None
        unscheduled = self._explain(eligible, windows, actions, mission_state, scenario, previous, outages, slew_by_satellite)
        details = self._solver_details(
            solver, status, use_baseline, weight,
            policy="utility_then_fairness",
            fallback_reason=fallback_reason,
            skip_reason="fewer than two identified requesters",
            fairness_population=identified_requesters,
            budget_allocation={"utility": self.deterministic_limit},
            achieved_gap=None,
            stability_result=None,
            stages=[{
                "stage": "utility",
                "status": solver.status_name(status),
                "objective": solver.objective_value if status in _SOLVED else None,
                "objective_bound": solver.best_objective_bound if status in _SOLVED else None,
                "objective_unit": "priority_utility",
                "budget": self.deterministic_limit,
            }],
            rebalanced_ids=(),
        )
        result = replace(baseline, actions=tuple(actions), unscheduled=tuple(unscheduled),
            mission_utility=utility, planner_name="cp_sat", planning_policy="utility_then_fairness",
            policy_version="requester-utility-v1", solver_details=details,
            planning_time_ms=(time.perf_counter() - started) * 1000)
        return replace(result, violation_count=len(validate_plan(scenario, mission_state, requests, windows, result, outages, contacts)))

    def _plan_staged_fairness(
        self, scenario, mission_state, requests, eligible, windows, frozen, reservations,
        previous, builder, baseline, slew_by_satellite, outages, weight,
        first_action_number, started, plan_id, identified_requesters, contacts=()
    ) -> MissionPlan:
        total_budget = self.deterministic_limit
        d_utility = round(total_budget * 0.4, 4)
        d_fairness = round(total_budget * 0.4, 4)
        d_stability = round(total_budget * 0.2, 4)
        budget_allocation = {"utility": d_utility, "fairness": d_fairness, "stability": d_stability}

        # Stage 1: Primary utility optimization
        builder.maximize_utility(previous, weight)
        solver1 = cp_model.CpSolver()
        solver1.parameters.num_search_workers = 1
        solver1.parameters.random_seed = 0
        solver1.parameters.max_deterministic_time = d_utility
        status1 = solver1.solve(builder.model)
        if status1 == cp_model.MODEL_INVALID:
            raise ValueError(f"Invalid CP-SAT model: {builder.model.validate()}")

        # Compute pure candidate priority utility if solved
        s1_candidate_utility = sum(c.request.priority * solver1.value(c.present) for c in builder.candidates) if status1 in _SOLVED else None
        stage_1_entry = {
            "stage": "utility",
            "status": solver1.status_name(status1),
            "objective": s1_candidate_utility,
            "objective_bound": s1_candidate_utility if status1 == cp_model.OPTIMAL else None,
            "objective_unit": "priority_utility",
            "budget": d_utility,
        }

        # If Stage 1 optimality is unproven, skip fairness and retain Stage 1 / baseline result
        if status1 != cp_model.OPTIMAL:
            imaging = self._selected_actions(solver1, status1, builder, first_action_number)
            utility = sum(r.priority for r in requests if r.id in {a.request_id for a in [*frozen, *imaging]})
            use_baseline = status1 not in _SOLVED or utility < baseline.mission_utility
            if use_baseline:
                actions = list(baseline.actions)
                utility = baseline.mission_utility
                fallback_reason = "utility_below_baseline" if status1 in _SOLVED else "solver_infeasible"
            else:
                actions = list(frozen) + self._with_downlinks(scenario, mission_state, reservations, frozen,
                                                              imaging, first_action_number)
                fallback_reason = None
            unscheduled = self._explain(eligible, windows, actions, mission_state, scenario, previous, outages, slew_by_satellite)
            details = self._solver_details(
                solver1, status1, use_baseline, weight,
                policy="utility_then_fairness",
                fallback_reason=fallback_reason,
                skip_reason="primary optimality unproven",
                fairness_population=identified_requesters,
                budget_allocation=budget_allocation,
                achieved_gap=None,
                stability_result=None,
                stages=[stage_1_entry],
                rebalanced_ids=(),
            )
            result = replace(baseline, actions=tuple(actions), unscheduled=tuple(unscheduled),
                mission_utility=utility, planner_name="cp_sat", planning_policy="utility_then_fairness",
                policy_version="requester-utility-v1", solver_details=details,
                planning_time_ms=(time.perf_counter() - started) * 1000)
            return replace(result, violation_count=len(validate_plan(scenario, mission_state, requests, windows, result, outages, contacts)))

        # Primary utility optimum is proven! Retain pre-fairness solution:
        pre_fairness_actions = self._selected_actions(solver1, status1, builder, first_action_number)
        pre_fairness_utility = sum(r.priority for r in requests if r.id in {a.request_id for a in [*frozen, *pre_fairness_actions]})
        proven_candidate_utility = sum(c.request.priority * solver1.value(c.present) for c in builder.candidates)

        # Hold primary candidate utility fixed for all subsequent stages:
        builder.model.add(sum(c.request.priority * c.present for c in builder.candidates) == proven_candidate_utility)

        # Stage 2: Fairness balancing (minimize requester utility gap)
        completed_ids = set(mission_state.completed_request_ids)
        frozen_req_ids = {a.request_id for a in imaging_actions(frozen)}
        u_vars = []
        for req_id in identified_requesters:
            constant_reqs = {r.id for r in requests if r.requester_id == req_id and (r.id in completed_ids or r.id in frozen_req_ids)}
            const_val = sum(r.priority for r in requests if r.id in constant_reqs)
            cand_terms = [c.request.priority * c.present for c in builder.candidates if c.request.requester_id == req_id]
            max_cand = sum(c.request.priority for c in builder.candidates if c.request.requester_id == req_id)
            u_var = builder.model.new_int_var(const_val, const_val + max_cand, f"u_{req_id}")
            builder.model.add(u_var == const_val + sum(cand_terms))
            u_vars.append(u_var)

        max_total_u = max(1, sum(r.priority for r in requests))
        max_u = builder.model.new_int_var(0, max_total_u, "max_requester_utility")
        min_u = builder.model.new_int_var(0, max_total_u, "min_requester_utility")
        builder.model.add_max_equality(max_u, u_vars)
        builder.model.add_min_equality(min_u, u_vars)
        gap = builder.model.new_int_var(0, max_total_u, "requester_gap")
        builder.model.add(gap == max_u - min_u)

        builder.model.minimize(gap)
        solver2 = cp_model.CpSolver()
        solver2.parameters.num_search_workers = 1
        solver2.parameters.random_seed = 0
        solver2.parameters.max_deterministic_time = d_fairness
        status2 = solver2.solve(builder.model)

        stage_2_entry = {
            "stage": "fairness",
            "status": solver2.status_name(status2),
            "objective": int(solver2.objective_value) if status2 in _SOLVED else None,
            "objective_bound": solver2.best_objective_bound if status2 in _SOLVED else None,
            "objective_unit": "priority_utility_gap",
            "budget": d_fairness,
        }

        if status2 not in _SOLVED:
            actions = list(frozen) + self._with_downlinks(scenario, mission_state, reservations, frozen,
                                                          pre_fairness_actions, first_action_number)
            utility = pre_fairness_utility
            unscheduled = self._explain(eligible, windows, actions, mission_state, scenario, previous, outages, slew_by_satellite)
            details = self._solver_details(
                solver1, status1, True, weight,
                policy="utility_then_fairness",
                fallback_reason="fairness_stage_failed",
                skip_reason=None,
                fairness_population=identified_requesters,
                budget_allocation=budget_allocation,
                achieved_gap=None,
                stability_result=None,
                stages=[stage_1_entry, stage_2_entry],
                rebalanced_ids=(),
            )
            result = replace(baseline, actions=tuple(actions), unscheduled=tuple(unscheduled),
                mission_utility=utility, planner_name="cp_sat", planning_policy="utility_then_fairness",
                policy_version="requester-utility-v1", solver_details=details,
                planning_time_ms=(time.perf_counter() - started) * 1000)
            return replace(result, violation_count=len(validate_plan(scenario, mission_state, requests, windows, result, outages, contacts)))

        achieved_gap = int(solver2.value(gap))

        # Stage 3: Stability preference
        if status2 == cp_model.OPTIMAL:
            builder.model.add(gap == achieved_gap)
        else:
            builder.model.add(gap <= achieved_gap)

        stability_terms = [
            int(c.request.id in previous and previous[c.request.id].window_id == c.window.id) * c.present
            for c in builder.candidates
        ]
        if builder.penalties:
            scale = sum(builder.penalty_ranges) + 1
            builder.model.maximize(sum(term * scale for term in stability_terms) - sum(builder.penalties))
        else:
            builder.model.maximize(sum(stability_terms))

        solver3 = cp_model.CpSolver()
        solver3.parameters.num_search_workers = 1
        solver3.parameters.random_seed = 0
        solver3.parameters.max_deterministic_time = d_stability
        status3 = solver3.solve(builder.model)

        stage_3_entry = {
            "stage": "stability",
            "status": solver3.status_name(status3),
            "objective": solver3.objective_value if status3 in _SOLVED else None,
            "objective_bound": solver3.best_objective_bound if status3 in _SOLVED else None,
            "objective_unit": "retained_window_count",
            "budget": d_stability,
        }

        if status3 in _SOLVED:
            final_solver = solver3
            # If Stage 2 was only FEASIBLE, Stage 3 optimal does not prove fairness optimality:
            final_status = cp_model.FEASIBLE if status2 != cp_model.OPTIMAL else status3
            stability_result = {
                "status": solver3.status_name(status3),
                "objective": solver3.objective_value,
                "objective_bound": solver3.best_objective_bound,
            }
        else:
            final_solver = solver2
            final_status = status2
            stability_result = {
                "status": solver3.status_name(status3),
                "fallback_to_stage_2": True,
            }

        final_imaging = self._selected_actions(final_solver, final_status, builder, first_action_number)
        final_utility = sum(r.priority for r in requests if r.id in {a.request_id for a in [*frozen, *final_imaging]})

        # Check greedy baseline floor:
        if final_utility < baseline.mission_utility:
            use_baseline = True
            fallback_reason = "utility_below_baseline"
            actions = list(baseline.actions)
            utility = baseline.mission_utility
            fairness_rebalanced_request_ids = set()
        else:
            use_baseline = False
            fallback_reason = None
            actions = list(frozen) + self._with_downlinks(scenario, mission_state, reservations, frozen,
                                                          final_imaging, first_action_number)
            utility = final_utility

            # Establish causality between pre-fairness and final solution:
            pre_actions_by_req = {a.request_id: a for a in pre_fairness_actions if a.request_id}
            final_actions_by_req = {a.request_id: a for a in final_imaging if a.request_id}
            # Symmetric difference of scheduled requests:
            rebalanced = set(pre_actions_by_req.keys()) ^ set(final_actions_by_req.keys())
            # Plus requests whose placement/window changed to accommodate fairness balancing:
            for req_id, pre_act in pre_actions_by_req.items():
                if req_id in final_actions_by_req:
                    fin_act = final_actions_by_req[req_id]
                    if pre_act.window_id != fin_act.window_id or pre_act.start != fin_act.start:
                        rebalanced.add(req_id)
            fairness_rebalanced_request_ids = rebalanced

        unscheduled = self._explain(
            eligible, windows, actions, mission_state, scenario, previous, outages, slew_by_satellite,
            rebalanced_ids=fairness_rebalanced_request_ids
        )
        details = self._solver_details(
            final_solver, final_status, use_baseline, weight,
            policy="utility_then_fairness",
            fallback_reason=fallback_reason,
            skip_reason=None,
            fairness_population=identified_requesters,
            budget_allocation=budget_allocation,
            achieved_gap=achieved_gap if not use_baseline else None,
            stability_result=stability_result,
            stages=[stage_1_entry, stage_2_entry, stage_3_entry],
            rebalanced_ids=fairness_rebalanced_request_ids,
        )
        result = replace(baseline, actions=tuple(actions), unscheduled=tuple(unscheduled),
            mission_utility=utility, planner_name="cp_sat", planning_policy="utility_then_fairness",
            policy_version="requester-utility-v1", solver_details=details,
            planning_time_ms=(time.perf_counter() - started) * 1000)
        return replace(result, violation_count=len(validate_plan(scenario, mission_state, requests, windows, result, outages, contacts)))

    @staticmethod
    def _selected_actions(solver: cp_model.CpSolver, status, builder: _ModelBuilder,
                          first_action_number: int) -> list[ScheduledAction]:
        if status not in _SOLVED:
            return []
        selected = sorted(
            ((c.request, c.window, solver.value(c.start)) for c in builder.candidates if solver.value(c.present)),
            key=lambda chosen: (chosen[2], chosen[0].id),
        )
        actions = []
        for number, (request, window, start) in enumerate(selected, first_action_number):
            instant = builder.origin + timedelta(seconds=start)
            actions.append(ScheduledAction(format_id(ACTION_ID_PREFIX, number), request.id,
                window.satellite_id, window.id, instant, instant + timedelta(seconds=request.duration_s),
                request.energy_cost_wh, request.storage_cost_mb))
        return actions

    def _solver_details(
        self, solver: cp_model.CpSolver, status, use_baseline: bool, weight: int,
        policy: str = "utility",
        fallback_reason: str | None = None,
        skip_reason: str | None = None,
        fairness_population: list[str] | None = None,
        budget_allocation: dict[str, float] | None = None,
        achieved_gap: int | None = None,
        stability_result: dict[str, Any] | None = None,
        stages: list[dict[str, Any]] | None = None,
        rebalanced_ids: Iterable[str] = (),
    ) -> dict[str, Any]:
        solved = status in _SOLVED
        return {
            "status": solver.status_name(status),
            "objective": solver.objective_value if solved else None,
            "objective_bound": solver.best_objective_bound if solved else None,
            "optimality_gap": (max(0.0, solver.best_objective_bound - solver.objective_value)
                               / max(1.0, abs(solver.objective_value))) if solved and not use_baseline else None,
            "fallback": use_baseline,
            "fallback_reason": fallback_reason,
            "skip_reason": skip_reason,
            "ortools_version": ortools.__version__,
            "workers": 1,
            "seed": 0,
            "max_deterministic_time": self.deterministic_limit,
            "objective_priority_weight": weight,
            "time_resolution_s": 1,
            "policy": policy,
            "policy_version": "requester-utility-v1",
            "fairness_population": fairness_population,
            "budget_allocation": budget_allocation or {"utility": self.deterministic_limit},
            "achieved_gap": achieved_gap,
            "achieved_gap_unit": "priority_utility_gap",
            "stability_result": stability_result,
            "stages": stages or [],
            "fairness_rebalanced_request_ids": sorted(rebalanced_ids),
        }

    @staticmethod
    def _with_downlinks(scenario, state, reservations, frozen, imaging, first_action_number):
        result = list(imaging)
        number = first_action_number + len(imaging)
        for satellite in sorted(scenario.satellites, key=lambda item: item.id):
            satellite_reservations = [r for r in reservations if r.satellite_id == satellite.id]
            projection = ResourceProjection.for_mission(scenario, state, satellite)
            for action in [*frozen, *imaging]:
                if action.satellite_id == satellite.id and action.status is ActionStatus.PLANNED:
                    projection.commit(action)
            for reservation in satellite_reservations:
                projection.commit(reservation)
            result.extend(finalize_downlinks(satellite_reservations, projection, number))
            number += len(satellite_reservations)
        return result

    @staticmethod
    def _explain(requests, windows, actions, state, scenario, previous, outages=(), slew_by_satellite=None, rebalanced_ids=None):
        outages = tuple(outages)
        slew_by_satellite = slew_by_satellite or {
            satellite.id: SlewModel.from_scenario(scenario, satellite, requests) for satellite in scenario.satellites
        }
        rebalanced_set = set(rebalanced_ids or ())
        actions_by_satellite: dict[str, list] = {satellite.id: [] for satellite in scenario.satellites}
        for action in actions:
            actions_by_satellite.setdefault(action.satellite_id, []).append(action)
        projections = {}
        for satellite in scenario.satellites:
            projection = ResourceProjection.for_mission(scenario, state, satellite)
            for action in actions_by_satellite.get(satellite.id, []):
                if action.status is ActionStatus.PLANNED:
                    projection.commit(action)
            projections[satellite.id] = projection
        selected_ids = {a.request_id for a in imaging_actions(actions)}
        entries = []
        for request in requests:
            if request.id in selected_ids:
                continue
            if request.id in rebalanced_set:
                entries.append(UnscheduledEntry(request.id, ReasonCode.REBALANCED_FOR_REQUESTER_SHARE))
                continue
            old_window = previous[request.id].window_id if request.id in previous else None
            violation = None
            any_candidates = False
            for satellite in _candidate_satellites(scenario, request):
                slew = slew_by_satellite[satellite.id]
                projection = projections[satellite.id]
                satellite_actions = actions_by_satellite.get(satellite.id, [])
                satellite_outages = tuple(
                    (start, end) for outage_satellite_id, start, end in outages
                    if outage_satellite_id == satellite.id
                )
                candidates = _ordered_candidates(
                    [w for w in windows if w.request_id == request.id and w.satellite_id == satellite.id],
                    old_window,
                )
                any_candidates = any_candidates or bool(candidates)
                for window in candidates:
                    start = max(window.start, state.simulated_time)
                    starts = _candidate_starts_in_window(
                        start, window.end, request.duration_s, satellite_actions, slew=slew, request_id=request.id
                    ) or [start]
                    for instant in starts:
                        end = instant + timedelta(seconds=request.duration_s)
                        violation = (check_window_containment(request.id, window, instant, end)
                            or check_deadline(request.id, request.deadline, end)
                            or check_satellite_availability(
                                request.id, state.for_satellite(satellite.id).available, instant, end, satellite_outages
                            )
                            or projection.check_commit(request.id, instant, request.energy_cost_wh, request.storage_cost_mb, satellite.storage_capacity_mb)
                            or check_overlap(request.id, instant, end, satellite_actions, slew=slew))
            reason = (_unscheduled_reason(violation, old_window) if any_candidates else
                      ReasonCode.NO_ALTERNATIVE_WINDOW if old_window else ReasonCode.NO_OBSERVATION_WINDOW)
            # A bounded optimizer can omit a feasible request; do not claim a broken window.
            if any_candidates and violation is None:
                reason = ReasonCode.DISPLACED_BY_COMPETING_REQUEST
            entries.append(UnscheduledEntry(request.id, reason))
        return entries
