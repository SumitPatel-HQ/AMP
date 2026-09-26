"""Decision 20: the one-command evaluation runner.

Drives `MissionSession` only (never a planner, constraint, or propagator
internal) for every case under `amis/data/evaluation/`, then checks four
blocking gates that no per-case pass rate can offset: zero violations,
frozen actions carried unchanged across a replan, replay equality (the
same scripted case reproduces the same plan from a fresh session), and
byte-identical reruns (two independent runs of the same scenario/planner
with no events produce the same plan). A case failure or a gate failure
both name the failing stage. Network access is blocked for the duration
of the run to prove the offline rule the spec asks for.
"""

from __future__ import annotations

import contextlib
import socket
import sys
from dataclasses import replace
from typing import Any

from amis.demo import build_demo_scenario
from amis.evaluation.cases import EvaluationCase, load_cases
from amis.evaluation.comparison import run_comparison
from amis.examples import examples as _examples
from amis.session import MissionSession
from amis.windows.selection import ScenarioWindowProvider
from amis.windows.synthetic import SyntheticWindowProvider

DISCLAIMER = (
    "Results come from a simulator over bundled example and generated "
    "missions. Nothing here is flight or operational certification."
)


class _EvaluationStageError(Exception):
    def __init__(self, stage: str, cause: Exception) -> None:
        super().__init__(f"{stage}: {cause}")
        self.stage = stage
        self.cause = cause


@contextlib.contextmanager
def _block_sockets():
    """Block outbound connections without breaking `socket.socket` as a base
    class (the stdlib `ssl` module subclasses it on import), so this only
    stops real network I/O rather than crashing unrelated imports."""

    def _blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("network access is disabled during the evaluation run")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]


def _scenario_and_provider(key: str):
    if key == "synthetic_demo":
        return build_demo_scenario(), SyntheticWindowProvider()
    if key == "synthetic_demo_unavailable":
        base = build_demo_scenario()
        return replace(base, satellite=replace(base.satellite, available=False)), SyntheticWindowProvider()
    catalogue = _examples()
    if key not in catalogue:
        raise ValueError(f"unknown scenario key: {key}")
    return catalogue[key], ScenarioWindowProvider()


def _run_script(case: EvaluationCase) -> dict[str, Any]:
    scenario, provider = _scenario_and_provider(case.scenario)
    session = MissionSession(window_provider=provider)
    session.load_scenario(scenario)
    session.generate_windows()
    session.select_planner(case.planner)
    plan = session.plan()
    observed_reasons = {entry.reason_code.value for entry in plan.unscheduled}

    for index, step in enumerate(case.steps):
        try:
            if "advance_seconds" in step:
                session.step(step["advance_seconds"])
            elif "event" in step:
                event = step["event"]
                session.inject_event(event["type"], event["payload"])
                impact = session.get_last_impact()
                for reasons in impact.reason_codes.values():
                    observed_reasons.update(reason.value for reason in reasons)
            elif step.get("replan"):
                previous = session.get_plan()
                plan = session.replan(expected_parent_plan_id=previous.id)
                observed_reasons.update(entry.reason_code.value for entry in plan.unscheduled)
                diff = session.compare_versions(previous.version, plan.version)
                observed_reasons.update(entry.reason_code.value for entry in diff.entries)
            else:
                raise ValueError(f"unknown step: {step}")
        except Exception as error:  # noqa: BLE001 - re-raised with a named stage below
            raise _EvaluationStageError(f"case:{case.id} step:{index}", error) from error

    final_plan = session.get_plan()
    return {
        "session": session,
        "final_plan": final_plan,
        "observed_reasons": observed_reasons,
    }


def _check_expectations(case: EvaluationCase, result: dict[str, Any]) -> list[str]:
    failures = []
    expect = case.expect
    plan = result["final_plan"]
    if "max_violations" in expect and plan.violation_count > expect["max_violations"]:
        failures.append(
            f"violation_count {plan.violation_count} exceeds max {expect['max_violations']}"
        )
    for reason in expect.get("reason_codes_include", ()):
        if reason not in result["observed_reasons"]:
            failures.append(f"expected reason code {reason} was not observed")
    if "min_explanation_coverage" in expect:
        coverage = result["session"].get_metrics(plan.id).explanation_coverage
        if coverage is None or coverage < expect["min_explanation_coverage"]:
            failures.append(f"explanation_coverage {coverage} below minimum {expect['min_explanation_coverage']}")
    return failures


def _plan_fingerprint(plan) -> dict[str, Any]:
    data = plan.to_dict()
    data.pop("planning_time_ms", None)
    data.pop("created_at", None)
    if data.get("solver_details"):
        data["solver_details"] = {
            k: v for k, v in data["solver_details"].items() if k != "max_deterministic_time"
        }
    return data


def _gate_replay_equality(case: EvaluationCase, first_result: dict[str, Any]) -> str | None:
    try:
        second_result = _run_script(case)
    except _EvaluationStageError as error:
        return f"case:{case.id} replay raised at {error.stage}: {error.cause}"
    if _plan_fingerprint(first_result["final_plan"]) != _plan_fingerprint(second_result["final_plan"]):
        return f"case:{case.id} replay produced a different final plan"
    return None


def _gate_byte_identical_rerun(case: EvaluationCase) -> str | None:
    if case.steps:
        return None  # only meaningful for a bare single plan() call
    scenario, provider = _scenario_and_provider(case.scenario)
    fingerprints = []
    for _ in range(2):
        session = MissionSession(window_provider=provider)
        session.load_scenario(scenario)
        session.generate_windows()
        session.select_planner(case.planner)
        fingerprints.append(_plan_fingerprint(session.plan()))
    if fingerprints[0] != fingerprints[1]:
        return f"case:{case.id} two independent plan() runs were not byte identical"
    return None


def _gate_frozen_actions_identical(case: EvaluationCase, result: dict[str, Any]) -> list[str]:
    failures = []
    session: MissionSession = result["session"]
    plans = session.get_plans()
    for previous, current in zip(plans, plans[1:]):
        current_by_id = {action.id: action for action in current.actions}
        for action in previous.actions:
            carried = current_by_id.get(action.id)
            if carried is not None and (carried.start, carried.end, carried.window_id) != (
                action.start, action.end, action.window_id,
            ):
                failures.append(
                    f"case:{case.id} frozen action {action.id} changed placement across replan"
                )
    return failures


def _run_planner_comparison_case(case: EvaluationCase) -> dict[str, Any]:
    utilities = {}
    for planner_name in ("greedy", "cp_sat"):
        result = _run_script(replace(case, planner=planner_name))
        utilities[planner_name] = result["final_plan"].mission_utility
    failures = []
    if case.expect.get("cp_sat_utility_at_least_greedy") and utilities["cp_sat"] < utilities["greedy"]:
        failures.append(
            f"cp_sat utility {utilities['cp_sat']} is below greedy utility {utilities['greedy']}"
        )
    return {
        "id": case.id, "category": case.category, "passed": not failures,
        "utilities": utilities, "failures": failures,
    }


def run_evaluation() -> dict[str, Any]:
    with _block_sockets():
        cases = load_cases()
        case_reports = []
        gate_failures: dict[str, list[str]] = {
            "zero_violations": [],
            "frozen_actions_identical": [],
            "replay_equality": [],
            "byte_identical_reruns": [],
        }

        for case in cases:
            if case.category == "planner_comparison":
                case_reports.append(_run_planner_comparison_case(case))
                continue
            try:
                result = _run_script(case)
            except _EvaluationStageError as error:
                case_reports.append({
                    "id": case.id, "category": case.category, "passed": False,
                    "stage": error.stage, "error": str(error.cause),
                })
                continue

            expectation_failures = _check_expectations(case, result)
            plan = result["final_plan"]
            if plan.violation_count > 0:
                gate_failures["zero_violations"].append(
                    f"case:{case.id} final plan carries {plan.violation_count} violation(s)"
                )
            gate_failures["frozen_actions_identical"].extend(
                _gate_frozen_actions_identical(case, result)
            )
            replay_failure = _gate_replay_equality(case, result)
            if replay_failure:
                gate_failures["replay_equality"].append(replay_failure)
            rerun_failure = _gate_byte_identical_rerun(case)
            if rerun_failure:
                gate_failures["byte_identical_reruns"].append(rerun_failure)

            case_reports.append({
                "id": case.id, "category": case.category,
                "passed": not expectation_failures,
                "violation_count": plan.violation_count,
                "observed_reason_codes": sorted(result["observed_reasons"]),
                "failures": expectation_failures,
            })

        comparison = run_comparison()

    gates = {
        name: {"passed": not failures, "failures": failures}
        for name, failures in gate_failures.items()
    }

    return {
        "disclaimer": DISCLAIMER,
        "case_count": len(cases),
        "cases": case_reports,
        "gates": gates,
        "comparison": comparison,
    }


def main() -> int:
    import json

    report = run_evaluation()
    print(report["disclaimer"])
    print(f"library versions: {report['comparison']['library_versions']}")
    print(f"cases run: {report['case_count']}")
    for case in report["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        stage = f" (stage {case['stage']}: {case.get('error')})" if "stage" in case else ""
        print(f"  [{status}] {case['category']}/{case['id']}{stage}")

    gates_passed = True
    for name, gate in report["gates"].items():
        status = "PASS" if gate["passed"] else "FAIL"
        print(f"gate [{status}] {name}")
        for failure in gate["failures"]:
            print(f"    - {failure}")
        gates_passed = gates_passed and gate["passed"]

    with open("evaluation-report.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)

    cases_passed = all(case["passed"] for case in report["cases"])
    return 0 if gates_passed and cases_passed else 1


if __name__ == "__main__":
    sys.exit(main())
