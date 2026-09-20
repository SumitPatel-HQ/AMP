"""WindowProvider protocol.

Window generation sits behind this interface so an orbital provider
(Skyfield or SGP4) can replace the synthetic one later without the
planner changing.
"""

from __future__ import annotations

from typing import Iterable, Protocol

from amis.domain import ObservationRequest, ObservationWindow, Scenario


class WindowProvider(Protocol):
    def generate(
        self, scenario: Scenario, requests: Iterable[ObservationRequest]
    ) -> list[ObservationWindow]: ...
