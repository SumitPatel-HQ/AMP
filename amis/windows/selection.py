"""Scenario-level provider dispatch; absence of policy preserves legacy dispatch."""

from typing import Iterable

from amis.demo import CanonicalWindowProvider, ProductionWindowProvider
from amis.domain import ObservationRequest, ObservationWindow, Scenario
from amis.windows.orbital import OrbitalWindowProvider
from amis.windows.synthetic import SyntheticWindowProvider
from amis.windows.protocol import WindowProvider


class ScenarioWindowProvider:
    def __init__(self, legacy: WindowProvider | None = None) -> None:
        self._providers: dict[str, WindowProvider] = {
            "synthetic": SyntheticWindowProvider(),
            "canonical_demo": CanonicalWindowProvider(),
            "orbital": OrbitalWindowProvider(),
        }
        self._legacy = legacy or ProductionWindowProvider()

    def generate(self, scenario: Scenario, requests: Iterable[ObservationRequest]) -> list[ObservationWindow]:
        if scenario.window_policy is None:
            return self._legacy.generate(scenario, requests)
        return self._providers[scenario.window_policy.provider].generate(scenario, requests)
