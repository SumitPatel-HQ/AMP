"""Builder-side engineering defaults for request resource costs.

Stored costs keep their current meaning: the planner and the constraint
engine read ``energy_cost_wh`` and ``storage_cost_mb`` as given. These
helpers only compute the starting values the scenario builder fills in,
so hand-computed values stay checkable without touching planning.
"""

from __future__ import annotations


def derive_energy_wh(power_w: float, duration_s: float) -> float:
    """Energy for one observation: power times duration, in watt-hours."""
    return power_w * duration_s / 3600.0


def derive_storage_mb(data_rate_mbps: float, duration_s: float) -> float:
    """Storage for one observation: data rate times duration, in megabytes."""
    return data_rate_mbps * duration_s / 8.0
