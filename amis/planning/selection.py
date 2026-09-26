"""Named planners for per-run selection."""
from amis.planning.protocol import Planner
from amis.planning.greedy import GreedyPlanner


def make_planner(name: str) -> Planner:
    if name == "greedy":
        return GreedyPlanner()
    if name == "cp_sat":
        from amis.planning.cp_sat import CpSatPlanner
        return CpSatPlanner()
    raise ValueError(f"Unknown planner: {name}")
