# Planner selection is per-run, and CP-SAT determinism is deliberate

A mission picks its planner by name (`"greedy"` or `"cp_sat"`) on `create_plan` and, optionally, on `replan`; the choice is recorded on the resulting `MissionPlan` as `planner_name` so a stored plan is self-describing without a side channel. `amis/planning/selection.py` maps the name to a planner instance; `MissionSession.select_planner` is the only thing that touches it. Nothing about the `Planner` protocol changed: `CpSatPlanner` builds a full CP-SAT model (one presence literal and optional interval per request-window pair, one no-overlap constraint across those plus the frozen actions, linear resource sums under the existing one-way model), then falls back to a `GreedyPlanner` baseline plan whenever the solver does not reach `OPTIMAL`/`FEASIBLE` or its utility would be lower than greedy's. A CP-SAT plan therefore never scores worse than the greedy plan it is compared against.

The solver runs single-threaded (`num_search_workers = 1`), with a fixed seed (`random_seed = 0`) and a work-based time limit (`max_deterministic_time`), not a wall-clock one. Solver status, objective, objective bound, optimality gap, whether the fallback fired, and the `ortools` version are recorded on the plan as `solver_details`, so a comparison report can cite an optimality gap without re-solving.

## Considered options

A wall-clock time limit was rejected: it makes two runs on different hardware, or under different machine load, solve to different points in the search and disagree on a plan for the same inputs. `max_deterministic_time` counts solver work, not seconds, which is what the evaluation suite's `byte_identical_reruns` gate depends on.

Letting CP-SAT report its own plan even when it scores below greedy was rejected. The second planner exists to prove near-optimal quality is reachable; a plan that a bounded search can't verify but happens to return anyway would sometimes silently regress mission utility relative to what the MVP already produces, which no operator asked for and no comparison report should have to caveat.

A separate table for solver runs was rejected in favor of one nullable JSON column (`solver_details`) on `mission_plans`. Nothing else in the schema needs to join against solver internals, and a greedy plan legitimately has none to record.

## Consequences

`amis/planning/greedy.py` needed no change: `CpSatPlanner` calls it directly for the baseline and for its explanation pass, so the two planners share one definition of "why is this request unscheduled" (`amis/planning/greedy.py`'s private helpers) rather than two.

A CP-SAT plan's `violation_count` is computed by running the same `validate_plan` check used everywhere else, after the solver returns, rather than trusted from the model. This is what let `amis/evaluation/runner.py`'s `zero_violations` gate treat both planners identically.

Because the deterministic limit bounds search effort and not wall time, a large mission can still return `FEASIBLE` rather than `OPTIMAL`; `solver_details.fallback` and `optimality_gap` exist so a report can say honestly that a plan is good-enough-and-verified rather than provably best.
