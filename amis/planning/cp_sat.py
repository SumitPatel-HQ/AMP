"""Deterministic optional-interval planner under the one-way resource model.

Wave 6 (ADR-0013): slew is sequence-dependent, which the no-overlap
interval model cannot express, so every interval carries the largest
pairwise slew gap as a conservative fixed gap. Sunlight recharge is left
out of the linear battery sum, which is also conservative. The greedy
baseline fallback keeps both gains whenever CP-SAT would do worse.

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
import time
from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Iterable

from ortools.sat.python import cp_model
import ortools

from amis.constraints import (ResourceProjection, check_deadline, check_overlap,
    check_satellite_availability, check_window_containment, validate_plan)
from amis.domain import (ActionStatus, ContactWindow, imaging_actions, MissionPlan, MissionState, ObservationRequest,
    ObservationWindow, ReasonCode, RequestStatus, Satellite, Scenario, ScheduledAction, UnscheduledEntry)
from amis.dynamics.slew import SlewModel
from amis.ids import ACTION_ID_PREFIX, FIRST_PLAN_ID, format_id
from amis.planning.downlink import finalize_downlinks, reserve_downlinks
from amis.planning.greedy import (GreedyPlanner, _frozen_actions, _ordered_candidates,
    _candidate_starts_in_window, _unscheduled_reason)


def _candidate_satellites(scenario: Scenario, request: ObservationRequest) -> list[Satellite]:
    if request.satellite_id is not None:
        return [scenario.satellite_by_id(request.satellite_id)]
    return sorted(scenario.satellites, key=lambda item: item.id)


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
        gap_s_by_satellite = {
            satellite.id: math.ceil(slew_by_satellite[satellite.id].max_gap_s([
                *(a.request_id for a in imaging_actions(frozen) if a.satellite_id == satellite.id),
                *(r.id for r in eligible if r.satellite_id in (None, satellite.id)),
            ]))
            for satellite in satellites
        }
        model = cp_model.CpModel()
        origin = scenario.start_time
        seconds = lambda instant: (instant - origin).total_seconds()
        intervals_by_satellite: dict[str, list] = {satellite.id: [] for satellite in satellites}
        for a in imaging_actions(frozen):
            gap_s = gap_s_by_satellite[a.satellite_id]
            intervals_by_satellite[a.satellite_id].append(model.new_fixed_size_interval_var(
                math.floor(seconds(a.start)), math.ceil(seconds(a.end)) - math.floor(seconds(a.start)) + gap_s,
                f"frozen_{a.id}"))
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
                gap_s = gap_s_by_satellite[window.satellite_id]
                duration = math.ceil(request.duration_s)
                low = math.ceil(seconds(max(window.start, mission_state.simulated_time, origin)))
                high = math.floor(seconds(min(window.end, request.deadline, scenario.end_time))) - duration
                if high < low:
                    continue
                present = model.new_bool_var(f"present_{window.id}")
                start = model.new_int_var(low, high, f"start_{window.id}")
                intervals_by_satellite[window.satellite_id].append(
                    model.new_optional_fixed_size_interval_var(start, duration + gap_s, present, window.id))
                literals.append(present)
                choices.append((request, window, present, start))
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
            model.add_no_overlap(intervals_by_satellite[satellite.id])
        # Downlink releases are ignored here: the linear sum is a conservative
        # bound on the timeline walk, and the greedy-baseline fallback keeps
        # downlink gains (ADR-0011).
        for satellite in satellites:
            committed = [
                a for a in imaging_actions(frozen)
                if a.status is ActionStatus.PLANNED and a.satellite_id == satellite.id
            ]
            satellite_state = mission_state.for_satellite(satellite.id)
            satellite_choices = [choice for choice in choices if choice[1].satellite_id == satellite.id]
            # Exact decimal ratios avoid rounding a resource budget into overcommitment.
            for attr, available in (("energy_cost_wh", satellite_state.battery_wh),
                                    ("storage_cost_mb", satellite.storage_capacity_mb - satellite_state.storage_usage_mb)):
                costs = [Fraction(str(getattr(r, attr))) for r, _, _, _ in satellite_choices]
                budget = Fraction(str(available)) - sum(Fraction(str(getattr(a, attr))) for a in committed)
                scale = math.lcm(budget.denominator, *(c.denominator for c in costs))
                coefficients = [int(c * scale) for c in costs]
                bound = int(budget * scale)
                if sum(abs(c) for c in coefficients) + abs(bound) >= 2**62:
                    raise ValueError("Resource precision exceeds CP-SAT integer range")
                model.add(sum(c * choice[2] for c, choice in zip(coefficients, satellite_choices)) <= max(0, bound))
                if bound < 0:
                    for _, _, present, _ in satellite_choices:
                        model.add(present == 0)
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
