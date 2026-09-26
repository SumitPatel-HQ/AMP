"""The Wave 5 threshold rule: archived cloud fractions become recorded blocks.

For each valid observation window the rule reads the normalized sample
closest to the window's culmination for that request's target. Coverage
at or above the threshold yields a ``CloudBlockPayload`` carrying the
sample's source, coverage, and the threshold it was judged against.
Below the threshold, or with no sample near the culmination, the window
is left alone and no payload is produced.

The rule is pure and offline: it never fetches, and the planner never
sees it. Callers inject each returned payload through the ordinary
``CLOUD_BLOCK`` path, so the event log stays the replay record
(ADR-0002) and a replay needs no archive and no network.
"""

from __future__ import annotations

import math
from datetime import datetime

from amis.domain import CloudBlockPayload, ObservationRequest, ObservationWindow
from amis.weather.samples import CloudSample


def culmination_time(window: ObservationWindow) -> datetime:
    """When the rule samples the weather: the stored peak, else the midpoint."""
    if window.peak_time is not None:
        return window.peak_time
    return window.start + (window.end - window.start) / 2


def coverage_at(
    samples: tuple[CloudSample, ...] | list[CloudSample],
    *,
    target_lat: float,
    target_lon: float,
    moment: datetime,
    tolerance_s: float = 1800.0,
) -> CloudSample | None:
    """The sample nearest ``moment`` at the exact target, within tolerance."""
    if not math.isfinite(tolerance_s) or tolerance_s <= 0:
        raise ValueError("sample tolerance must be a positive number of seconds")
    best: CloudSample | None = None
    best_gap = tolerance_s
    for sample in samples:
        if sample.target_lat != target_lat or sample.target_lon != target_lon:
            continue
        gap = abs((sample.time - moment).total_seconds())
        if gap <= best_gap and (
            best is None or gap < best_gap or sample.time < best.time
        ):
            best = sample
            best_gap = gap
    return best


def cloud_block_payloads_for_windows(
    samples: tuple[CloudSample, ...] | list[CloudSample],
    requests: tuple[ObservationRequest, ...] | list[ObservationRequest],
    windows: tuple[ObservationWindow, ...] | list[ObservationWindow],
    *,
    threshold_pct: float,
    tolerance_s: float = 1800.0,
) -> list[CloudBlockPayload]:
    """Convert coverage samples into cloud-block payloads, in window order.

    Only valid windows are considered: a window an earlier event already
    blocked keeps its recorded cause. Coverage exactly at the threshold
    blocks, so the rule reads as "cloudier than allowed".
    """
    if (
        not math.isfinite(threshold_pct)
        or threshold_pct < 0
        or threshold_pct > 100
    ):
        raise ValueError("cloud threshold must be a percentage")
    targets = {request.id: request for request in requests}
    payloads: list[CloudBlockPayload] = []
    for window in sorted(windows, key=lambda item: (item.start, item.id)):
        if not window.valid:
            continue
        request = targets.get(window.request_id)
        if request is None:
            raise ValueError(
                f"window {window.id} names an unknown request {window.request_id}"
            )
        sample = coverage_at(
            samples,
            target_lat=request.target_lat,
            target_lon=request.target_lon,
            moment=culmination_time(window),
            tolerance_s=tolerance_s,
        )
        if sample is None or sample.cloud_cover_pct < threshold_pct:
            continue
        payloads.append(
            CloudBlockPayload(
                request_id=window.request_id,
                window_id=window.id,
                source=sample.source,
                cloud_cover_pct=sample.cloud_cover_pct,
                threshold_pct=threshold_pct,
            )
        )
    return payloads
