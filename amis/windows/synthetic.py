"""SyntheticWindowProvider: deterministic windows from scenario configuration.

Depends only on the scenario and requests, so two runs of the same
scenario produce identical windows.
"""

from __future__ import annotations

from typing import Iterable

from amis.domain import ObservationRequest, ObservationWindow, Scenario


class SyntheticWindowProvider:
    def generate(
        self, scenario: Scenario, requests: Iterable[ObservationRequest]
    ) -> list[ObservationWindow]:
        return [
            ObservationWindow(
                id=f"WIN-{request.id}-1",
                request_id=request.id,
                satellite_id=scenario.satellite.id,
                start=scenario.start_time,
                end=scenario.end_time,
                valid=True,
                invalid_reason=None,
            )
            for request in requests
        ]
