"""Wave 2: proof of quality — planner selection, CP-SAT determinism, evaluation suite (ADR-0009).

Drives MissionSession and the evaluation runner's public gates; never asserts
on propagator, solver, or component internals beyond the plan outputs
(planner_name, solver_details) the spec requires to be recorded.
"""

from __future__ import annotations

import socket

import pytest

from amis.demo import build_demo_scenario
from amis.domain import ReasonCode
from amis.evaluation import cases as evaluation_cases
from amis.evaluation import comparison as evaluation_comparison
from amis.evaluation import runner as evaluation_runner
from amis.planning.selection import make_planner
from amis.session import MissionSession
from amis.windows import SyntheticWindowProvider


def _session(planner="greedy"):
    session = MissionSession(window_provider=SyntheticWindowProvider())
    session.load_scenario(build_demo_scenario())
    session.generate_windows()
    session.select_planner(planner)
    return session


def test_planner_choice_is_recorded_per_run():
    greedy = _session("greedy").plan()
    cp_sat = _session("cp_sat").plan()

    assert greedy.planner_name == "greedy"
    assert greedy.solver_details is None
    assert cp_sat.planner_name == "cp_sat"
    assert cp_sat.solver_details is not None


def test_unknown_planner_name_is_rejected():
    with pytest.raises(ValueError, match="Unknown planner"):
        make_planner("optimal")


def test_cp_sat_uses_deterministic_settings_and_records_gap():
    plan = _session("cp_sat").plan()
    details = plan.solver_details

    assert details["workers"] == 1
    assert details["seed"] == 0
    assert details["max_deterministic_time"] == pytest.approx(1.0)
    assert details["time_resolution_s"] == 1
    assert details["status"] in ("OPTIMAL", "FEASIBLE")
    assert details["ortools_version"]
    assert details["fallback"] is False
    assert details["optimality_gap"] is not None and details["optimality_gap"] >= 0.0


def test_cp_sat_reruns_are_byte_identical():
    first = _session("cp_sat").plan()
    second = _session("cp_sat").plan()

    assert evaluation_runner._plan_fingerprint(first) == evaluation_runner._plan_fingerprint(second)


def test_both_planners_return_zero_violations_on_the_demo():
    for planner in ("greedy", "cp_sat"):
        assert _session(planner).plan().violation_count == 0


def test_cp_sat_utility_is_at_least_greedy_on_the_demo():
    assert _session("cp_sat").plan().mission_utility >= _session("greedy").plan().mission_utility


def test_evaluation_covers_all_seven_categories():
    categories = {case.category for case in evaluation_cases.load_cases()}

    assert categories == {
        "smoke", "constraint", "event_response", "orbital_window",
        "explanation", "planner_comparison", "determinism",
    }


def test_evaluation_expectations_stay_independent_of_planner_output():
    allowed = {"max_violations", "reason_codes_include", "min_explanation_coverage",
               "cp_sat_utility_at_least_greedy"}
    for case in evaluation_cases.load_cases():
        assert set(case.expect) <= allowed, case.id


def test_every_reason_code_is_covered_by_a_case_expectation():
    covered = set()
    for case in evaluation_cases.load_cases():
        covered.update(case.expect.get("reason_codes_include", ()))

    assert covered == {code.value for code in ReasonCode}


def test_both_planners_return_zero_violations_on_every_case():
    from dataclasses import replace

    for case in evaluation_cases.load_cases():
        if case.category == "planner_comparison":
            continue
        for planner in ("greedy", "cp_sat"):
            result = evaluation_runner._run_script(replace(case, planner=planner))
            assert result["final_plan"].violation_count == 0, (case.id, planner)


def test_cp_sat_utility_is_at_least_greedy_on_the_comparison_case():
    case = next(
        case for case in evaluation_cases.load_cases()
        if case.category == "planner_comparison"
    )
    report = evaluation_runner._run_planner_comparison_case(case)

    assert report["passed"] is True
    assert report["utilities"]["cp_sat"] >= report["utilities"]["greedy"]


def test_byte_identical_rerun_gate_passes_for_bare_cases():
    for case in evaluation_cases.load_cases():
        if case.steps:
            continue
        assert evaluation_runner._gate_byte_identical_rerun(case) is None, case.id


def test_replay_equality_gate_passes_for_every_case():
    for case in evaluation_cases.load_cases():
        if case.category == "planner_comparison":
            continue
        result = evaluation_runner._run_script(case)
        assert evaluation_runner._gate_replay_equality(case, result) is None, case.id


def test_frozen_actions_survive_replans_identically():
    for case in evaluation_cases.load_cases():
        if case.category == "planner_comparison":
            continue
        result = evaluation_runner._run_script(case)
        assert evaluation_runner._gate_frozen_actions_identical(case, result) == [], case.id


def _namespace(**kwargs):
    return type("Plan", (), kwargs)()


def test_expectation_check_rejects_excess_violations():
    from dataclasses import replace

    case = next(iter(evaluation_cases.load_cases()))
    result = evaluation_runner._run_script(case)
    over_limit = replace(case, expect={**case.expect, "max_violations": -1})
    missing_reason = replace(case, expect={"reason_codes_include": ["NO_SUCH_REASON"]})

    assert evaluation_runner._check_expectations(over_limit, result) != []
    assert evaluation_runner._check_expectations(missing_reason, result) != []


def test_frozen_gate_catches_a_moved_frozen_action():
    from dataclasses import replace
    from datetime import timedelta

    from amis.demo import CanonicalWindowProvider, build_canonical_replan_scenario

    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(build_canonical_replan_scenario())
    session.generate_windows()
    first = session.plan()
    session.step(300)  # freeze OBS-A, matching the canonical replan demo
    second = session.replan()
    tampered = replace(
        second.actions[0], start=second.actions[0].start + timedelta(seconds=60),
        end=second.actions[0].end + timedelta(seconds=60),
    )
    tampered_plan = replace(second, actions=(tampered, *second.actions[1:]))
    fake_session = _namespace(get_plans=lambda self: (first, tampered_plan))

    assert evaluation_runner._gate_frozen_actions_identical(
        next(iter(evaluation_cases.load_cases())), {"session": fake_session}
    ) != []


def test_runner_stage_errors_name_the_failing_stage():
    from dataclasses import replace

    case = next(iter(evaluation_cases.load_cases()))
    broken = replace(case, steps=({"bogus_step": True},))

    with pytest.raises(evaluation_runner._EvaluationStageError) as raised:
        evaluation_runner._run_script(broken)

    assert raised.value.stage.startswith(f"case:{case.id} step:0")


def test_runner_blocks_network_access():
    with evaluation_runner._block_sockets():
        with pytest.raises(OSError, match="network access is disabled"):
            socket.socket().connect(("example.com", 80))

    # Restored afterwards: creating a socket object itself still works.
    assert socket.socket() is not None


def test_runner_report_carries_the_simulator_disclaimer():
    assert "simulator" in evaluation_runner.DISCLAIMER


def test_comparison_covers_examples_and_generated_orbital_missions():
    report = evaluation_comparison.run_comparison()

    assert report["data_origin"]
    assert report["library_versions"].get("ortools")
    by_scenario = {run["scenario_id"] for run in report["runs"] if "skipped" not in run}
    assert len(by_scenario) >= 4  # three examples plus generated orbital missions
    assert any("-N" in scenario_id for scenario_id in by_scenario)
    for run in report["runs"]:
        if "skipped" in run:
            continue
        assert run["planner"] in ("greedy", "cp_sat")
        for key in ("mission_utility", "scheduled_count", "violation_count",
                    "planning_time_ms", "plan_churn", "optimality_gap"):
            assert key in run
    assert {run["with_event"] for run in report["runs"]} == {False, True}
    assert report["summary"]["cp_sat"]["total_utility"] >= report["summary"]["greedy"]["total_utility"]
    assert report["summary"]["greedy"]["total_violations"] == 0
    assert report["summary"]["greedy"]["planning_time_median_ms"] is not None
