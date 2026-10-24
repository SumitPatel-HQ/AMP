"""Named planners for per-run selection."""
from amis.planning.protocol import Planner
from amis.planning.greedy import GreedyPlanner

VALID_POLICIES = ("utility", "utility_then_fairness")


def make_planner(name: str, policy: str = "utility", deterministic_limit: float = 1.0) -> Planner:
    if policy not in VALID_POLICIES:
        raise ValueError(f"Unknown planning policy: '{policy}'. Expected one of: {', '.join(VALID_POLICIES)}")
    if name == "greedy":
        if policy != "utility":
            raise ValueError(f"Planning policy '{policy}' is not supported with planner 'greedy'")
        return GreedyPlanner()
    if name == "cp_sat":
        from amis.planning.cp_sat import CpSatPlanner
        return CpSatPlanner(deterministic_limit=deterministic_limit, policy=policy)
    raise ValueError(f"Unknown planner: {name}")
