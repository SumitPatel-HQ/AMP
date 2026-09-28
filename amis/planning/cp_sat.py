"""Deterministic optional-interval planner under the one-way resource model.

Wave 6 (ADR-0013): slew is a sequence-dependent setup time. Every pair of
actions on one satellite gets an order literal, and the pair's own slew
gap is enforced in whichever order the solver picks. With sunlight
recharge, the battery is a chain of levels over short time buckets (see
`_add_recharge_battery_budget`), sound under the capacity cap. Downlink releases stay out of the storage sum,
and the greedy baseline fallback keeps that gain.

Wave 7 (ADR-0014): every no-overlap group and every resource budget is
scoped to one satellite. A window already names the satellite it was
computed against, so "at most one window chosen" (summed across every
candidate window of a request, on any of its candidate satellites)
is exactly the assignment rule: a request lands on at most one
satellite, decided by the objective rather than a separate assignment
stage.
"""
from __future__ import annotations

import math
from itertools import combinations
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, Iterable

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


def _candidate_satellites(scenario: Scenario, request: ObservationRequest) -> list[Satellite]:
    if request.satellite_id is not None:
        return [scenario.satellite_by_id(request.satellite_id)]
    return sorted(scenario.satellites, key=lambda item: item.id)


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


_BUCKET_S = 600


def _add_recharge_battery_budget(model: cp_model.CpModel, items: list[_Item], recharge: RechargeModel,
                                 initial_wh: float, capacity_wh: float,
                                 simulated_time: datetime, origin: datetime) -> None:
    """Battery as a chain of levels over short time buckets.

    Buckets end at every sunlit edge and at least every ``_BUCKET_S``
    seconds. ``level[b]`` is a lower bound on the battery when bucket ``b``
    opens. Everything spent in a bucket must fit its opening level, so no
    in-bucket gain is ever credited before a spend. The capped walk ends
    the bucket with at least ``min(level + gain, C) - spend``, so the next
    level is bounded by both ``level + gain - spend`` and ``C - spend``.
    Gain is floored and capacity floored, so rounding never overstates the
    battery. Frozen actions are exempt (ADR-0003): a bucket only has to fit
    when a candidate lands in it, and a deficit carries forward, blocking
    later candidates until recharge repays it.
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
    edges = sorted(edges)
    buckets = list(zip(edges, edges[1:]))
    gains = [math.floor(Fraction(recharge.gain_wh(max(simulated_time, origin + timedelta(seconds=low)),
                                                   origin + timedelta(seconds=high))) * scale)
             for low, high in buckets]

    spend_terms: list[list[Any]] = [[] for _ in buckets]
    fixed_spend = [0] * len(buckets)
    landings: list[list[Any]] = [[] for _ in buckets]
    for item, cost in zip(paid, scaled):
        spans = [index for index, (low, high) in enumerate(buckets) if low <= item.high and item.low < high]
        if item.fixed:
            fixed_spend[spans[0]] += cost
            continue
        if len(spans) == 1:
            memberships = [(spans[0], item.present)]
        else:
            memberships = []
            for index in spans:
                inside = model.new_bool_var("")
                low, high = buckets[index]
                model.add(item.start >= low).only_enforce_if(inside)
                model.add(item.start < high).only_enforce_if(inside)
                memberships.append((index, inside))
            model.add(sum(inside for _, inside in memberships) == item.present)
        for index, inside in memberships:
            spend_terms[index].append(cost * inside)
            landings[index].append(inside)

    total = sum(scaled)
    ceiling = math.floor(initial * scale) + sum(gains)
    if capacity is not None:
        ceiling = max(math.floor(initial * scale), min(ceiling, math.floor(capacity * scale)))
    level = model.new_constant(math.floor(initial * scale))
    for index in range(len(buckets)):
        spend = sum(spend_terms[index]) + fixed_spend[index]
        for landing in landings[index]:
            model.add(spend <= level).only_enforce_if(landing)
        following = model.new_int_var(-total, ceiling, f"battery_{index}")
        model.add(following <= level + gains[index] - spend)
        if capacity is not None:
            model.add(following <= math.floor(capacity * scale) - spend)
        level = following


class CpSatPlanner:
    def __init__(self, deterministic_limit: float = 1.0) -> None:
        if not math.isfinite(deterministic_limit) or deterministic_limit <= 0:
            raise ValueError("deterministic_limit must be positive and finite")
        self.deterministic_limit = deterministic_limit

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
        satellites = sorted(scenario.satellites, key=lambda item: item.id)
        slew_by_satellite = {
            satellite.id: SlewModel.from_scenario(scenario, satellite, requests) for satellite in satellites
        }
        culmination = bool(scenario.window_policy and scenario.window_policy.culmination_placement)
        baseline = GreedyPlanner().plan(scenario, mission_state, requests, windows,
                                       previous_plan, plan_id, first_action_number, outages, contacts)
        frozen = _frozen_actions(previous_plan, mission_state)
        frozen_ids = {a.request_id for a in imaging_actions(frozen)}
        eligible = [r for r in requests if r.id not in frozen_ids
                    and r.status not in (RequestStatus.COMPLETED, RequestStatus.EXPIRED)]
        previous = {a.request_id: a for a in imaging_actions(previous_plan.actions)} if previous_plan else {}
        model = cp_model.CpModel()
        origin = scenario.start_time
        seconds = lambda instant: (instant - origin).total_seconds()
        intervals_by_satellite: dict[str, list] = {satellite.id: [] for satellite in satellites}
        items_by_satellite: dict[str, list[_Item]] = {satellite.id: [] for satellite in satellites}
        for a in imaging_actions(frozen):
            fixed_start = math.floor(seconds(a.start))
            fixed_duration = math.ceil(seconds(a.end)) - fixed_start
            intervals_by_satellite[a.satellite_id].append(
                model.new_fixed_size_interval_var(fixed_start, fixed_duration, f"frozen_{a.id}"))
            items_by_satellite[a.satellite_id].append(_Item(
                a.request_id, True, fixed_start, fixed_duration, fixed_start, fixed_start,
                a if a.status is ActionStatus.PLANNED else None))
        choices = []
        penalties = []
        penalty_ranges = []
        outage_count = 0
        for request in eligible:
            candidate_ids = {satellite.id for satellite in _candidate_satellites(scenario, request)}
            literals = []
            for window in windows:
                if (
                    window.request_id != request.id
                    or window.satellite_id not in candidate_ids
                    or not window.valid
                    or not mission_state.for_satellite(window.satellite_id).available
                ):
                    continue
                duration = math.ceil(request.duration_s)
                low = math.ceil(seconds(max(window.start, mission_state.simulated_time, origin)))
                high = math.floor(seconds(min(window.end, request.deadline, scenario.end_time))) - duration
                if high < low:
                    continue
                present = model.new_bool_var(f"present_{window.id}")
                start = model.new_int_var(low, high, f"start_{window.id}")
                intervals_by_satellite[window.satellite_id].append(
                    model.new_optional_fixed_size_interval_var(start, duration, present, window.id))
                literals.append(present)
                choices.append((request, window, present, start))
                items_by_satellite[window.satellite_id].append(
                    _Item(request.id, present, start, duration, low, high, request))
                for outage_satellite_id, outage_start, outage_end in outages:
                    if outage_satellite_id != window.satellite_id:
                        continue
                    forbidden_low = math.ceil(seconds(outage_start)) - duration
                    forbidden_high = math.ceil(seconds(outage_end))
                    if forbidden_high < low or forbidden_low > high:
                        continue
                    before = model.new_bool_var(f"outage_before_{outage_count}")
                    after = model.new_bool_var(f"outage_after_{outage_count}")
                    outage_count += 1
                    model.add(start + duration <= math.ceil(seconds(outage_start))).only_enforce_if(before)
                    model.add(start + duration > math.ceil(seconds(outage_start))).only_enforce_if(before.Not())
                    model.add(start >= math.ceil(seconds(outage_end))).only_enforce_if(after)
                    model.add(start < math.ceil(seconds(outage_end))).only_enforce_if(after.Not())
                    model.add_bool_or([before, after]).only_enforce_if(present)
                if culmination and window.peak_time is not None:
                    centered = int(round(seconds(window.peak_time - timedelta(seconds=request.duration_s / 2))))
                    target = min(high, max(low, centered))
                    penalty = model.new_int_var(0, high - low, f"culm_{window.id}")
                    model.add(penalty >= start - target).only_enforce_if(present)
                    model.add(penalty >= target - start).only_enforce_if(present)
                    penalties.append(penalty)
                    penalty_ranges.append(high - low)
            # At most one (satellite, window) chosen across every candidate:
            # the assignment decision falls out of this same constraint.
            model.add(sum(literals) <= 1)
        for satellite in satellites:
            items = items_by_satellite[satellite.id]
            model.add_no_overlap(intervals_by_satellite[satellite.id])
            recharge = recharge_model(scenario, satellite)
            _add_pairwise_slew(model, items, slew_by_satellite[satellite.id])
            satellite_state = mission_state.for_satellite(satellite.id)
            _add_linear_budget(model, items, "storage_cost_mb",
                               satellite.storage_capacity_mb - satellite_state.storage_usage_mb)
            if recharge.recharge_rate_w > 0:
                _add_recharge_battery_budget(model, items, recharge, satellite_state.battery_wh,
                                             satellite.battery_capacity_wh, mission_state.simulated_time, origin)
            else:
                _add_linear_budget(model, items, "energy_cost_wh", satellite_state.battery_wh)
        weight = len(eligible) + 1
        priority_terms = [(r.priority * weight + int(r.id in previous and previous[r.id].window_id == w.id)) * x
                          for r, w, x, _ in choices]
        if penalties:
            # Geometry tie-break only: scale priority above any possible
            # total culmination distance so the preference never displaces
            # a higher-utility selection.
            scale = sum(penalty_ranges) + 1
            model.maximize(sum(coef * scale for coef in priority_terms) - sum(penalties))
        else:
            model.maximize(sum(priority_terms))
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 0
        solver.parameters.max_deterministic_time = self.deterministic_limit
        status = solver.solve(model)
        if status == cp_model.MODEL_INVALID:
            raise ValueError(f"Invalid CP-SAT model: {model.validate()}")
        selected = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            selected = [(r, w, solver.value(s)) for r, w, x, s in choices if solver.value(x)]
        actions = list(frozen)
        for number, (r, w, start) in enumerate(sorted(selected, key=lambda v: (v[2], v[0].id)), first_action_number):
            instant = origin + timedelta(seconds=start)
            actions.append(ScheduledAction(format_id(ACTION_ID_PREFIX, number), r.id,
                w.satellite_id, w.id, instant, instant + timedelta(seconds=r.duration_s),
                r.energy_cost_wh, r.storage_cost_mb))
        utility = sum(r.priority for r in requests if r.id in {a.request_id for a in actions})
        # A bounded search must never degrade the existing feasible baseline.
        use_baseline = status not in (cp_model.OPTIMAL, cp_model.FEASIBLE) or utility < baseline.mission_utility
        if use_baseline:
            actions = list(baseline.actions)
            utility = baseline.mission_utility
        else:
            actions = list(frozen) + self._with_downlinks(scenario, mission_state, contacts, frozen,
                                                          actions[len(frozen):], first_action_number)
        unscheduled = self._explain(eligible, windows, actions, mission_state, scenario, previous, outages, slew_by_satellite)
        result = replace(baseline, actions=tuple(actions), unscheduled=tuple(unscheduled),
            mission_utility=utility, planner_name="cp_sat", solver_details={
                "status": solver.status_name(status), "objective": solver.objective_value if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
                "objective_bound": solver.best_objective_bound if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
                "optimality_gap": (max(0.0, solver.best_objective_bound - solver.objective_value) / max(1.0, abs(solver.objective_value))) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) and not use_baseline else None,
                "fallback": use_baseline, "ortools_version": ortools.__version__,
                "workers": 1, "seed": 0, "max_deterministic_time": self.deterministic_limit,
                "objective_priority_weight": weight, "time_resolution_s": 1,
            }, planning_time_ms=(time.perf_counter() - started) * 1000)
        return replace(result, violation_count=len(validate_plan(scenario, mission_state, requests, windows, result, outages, contacts)))

    @staticmethod
    def _with_downlinks(scenario, state, contacts, frozen, imaging, first_action_number):
        """Imaging selection plus the downlink reservations that free storage.

        Reservations already name their own satellite; each satellite gets
        its own projection and its own numbering slice (Wave 7, ADR-0014).
        """
        reservations = reserve_downlinks(scenario, state, contacts, frozen)
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
    def _explain(requests, windows, actions, state, scenario, previous, outages=(), slew_by_satellite=None):
        outages = tuple(outages)
        slew_by_satellite = slew_by_satellite or {
            satellite.id: SlewModel.from_scenario(scenario, satellite, requests) for satellite in scenario.satellites
        }
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
