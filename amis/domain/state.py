"""MissionState: a value snapshot of the mission at one simulated instant."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from amis.domain.scenario import Scenario


@dataclass(frozen=True)
class MissionState:
    scenario_id: str
    simulated_time: datetime
    satellite_id: str
    battery_wh: float
    storage_usage_mb: float
    available: bool
    active_event_ids: tuple[str, ...] = field(default_factory=tuple)
    completed_request_ids: tuple[str, ...] = field(default_factory=tuple)
    mission_complete: bool = False

    @staticmethod
    def initial(scenario: Scenario) -> "MissionState":
        return MissionState(
            scenario_id=scenario.id,
            simulated_time=scenario.start_time,
            satellite_id=scenario.satellite.id,
            battery_wh=scenario.satellite.battery_charge_wh,
            storage_usage_mb=scenario.satellite.storage_usage_mb,
            available=scenario.satellite.available,
        )
