"""MissionSession: the single in-process test seam.

Integration tests drive this facade rather than HTTP. See
docs/adr/0001-mission-session-as-the-single-test-seam.md. Every
method returns domain objects, never a framework-specific type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

from amis.domain import MissionPlan, MissionState, ObservationWindow, Scenario
from amis.planning import GreedyPlanner
from amis.windows import SyntheticWindowProvider


class MissionSession:
    def __init__(self) -> None:
        self._scenario: Scenario | None = None
        self._windows: list[ObservationWindow] = []
        self._plan: MissionPlan | None = None
        self._window_provider = SyntheticWindowProvider()
        self._planner = GreedyPlanner()

    def load_scenario(self, source: Union[Scenario, dict[str, Any], str, Path]) -> Scenario:
        if isinstance(source, Scenario):
            scenario = source
        elif isinstance(source, (str, Path)):
            scenario = Scenario.from_dict(json.loads(Path(source).read_text()))
        else:
            scenario = Scenario.from_dict(source)

        self._scenario = scenario
        self._windows = []
        self._plan = None
        return scenario

    def generate_windows(self) -> list[ObservationWindow]:
        scenario = self._require_scenario()
        self._windows = self._window_provider.generate(scenario, scenario.requests)
        return list(self._windows)

    def plan(self) -> MissionPlan:
        scenario = self._require_scenario()
        mission_state = MissionState.initial(scenario)
        self._plan = self._planner.plan(
            scenario, mission_state, scenario.requests, self._windows
        )
        return self._plan

    def _require_scenario(self) -> Scenario:
        if self._scenario is None:
            raise ValueError("no scenario loaded")
        return self._scenario
