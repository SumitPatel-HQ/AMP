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
        # Wave 7 (ADR-0014): a request naming a satellite gets one window
        # against it; an unassigned request gets one per satellite, so the
        # planner has a candidate on every satellite it could be assigned to.
        # A single-satellite mission keeps the pre-Wave-7 id exactly
        # (`WIN-{request}-1`), so old plans stay byte identical.
        single = len(scenario.satellites) == 1
        windows = []
        for request in requests:
            satellite_ids = (
                [request.satellite_id]
                if request.satellite_id is not None
                else [satellite.id for satellite in scenario.satellites]
            )
            for satellite_id in satellite_ids:
                window_id = (
                    f"WIN-{request.id}-1" if single else f"WIN-{request.id}-{satellite_id}-1"
                )
                windows.append(ObservationWindow(
                    id=window_id,
                    request_id=request.id,
                    satellite_id=satellite_id,
                    start=scenario.start_time,
                    end=scenario.end_time,
                    valid=True,
                    invalid_reason=None,
                ))
        return windows
