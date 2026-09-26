"""Wave 5: the threshold rule maps coverage samples to the expected blocks."""

from datetime import datetime, timedelta, timezone

import pytest

from amis.domain import ObservationRequest, ObservationWindow
from amis.weather import (
    cloud_block_payloads_for_windows,
    coverage_at,
    culmination_time,
    load_archive,
    normalize_archive,
)
from amis.weather.samples import CloudSample

BLR = (12.97, 77.59)
T0 = datetime(2026, 9, 25, 6, tzinfo=timezone.utc)


def _request(request_id="OBS-BLR", lat=BLR[0], lon=BLR[1]) -> ObservationRequest:
    return ObservationRequest(
        id=request_id,
        target_lat=lat,
        target_lon=lon,
        priority=5,
        duration_s=60.0,
        deadline=T0 + timedelta(hours=3),
        energy_cost_wh=10.0,
        storage_cost_mb=10.0,
    )


def _window(
    window_id="WIN-OBS-BLR-1",
    request_id="OBS-BLR",
    start=T0,
    end=None,
    peak=None,
    valid=True,
) -> ObservationWindow:
    return ObservationWindow(
        id=window_id,
        request_id=request_id,
        satellite_id="SAT-001",
        start=start,
        end=start + timedelta(minutes=10) if end is None else end,
        valid=valid,
        peak_time=peak,
    )


def _sample(
    coverage,
    time=T0,
    lat=BLR[0],
    lon=BLR[1],
    source="open-meteo-archive",
) -> CloudSample:
    return CloudSample(
        target_lat=lat,
        target_lon=lon,
        time=time,
        cloud_cover_pct=coverage,
        source=source,
    )


def test_coverage_above_threshold_becomes_a_block_with_evidence():
    payloads = cloud_block_payloads_for_windows(
        [_sample(85.0)],
        [_request()],
        [_window(peak=T0)],
        threshold_pct=50.0,
    )

    assert len(payloads) == 1
    payload = payloads[0]
    assert (payload.request_id, payload.window_id) == ("OBS-BLR", "WIN-OBS-BLR-1")
    assert payload.source == "open-meteo-archive"
    assert payload.cloud_cover_pct == 85.0
    assert payload.threshold_pct == 50.0


def test_coverage_at_threshold_blocks():
    payloads = cloud_block_payloads_for_windows(
        [_sample(50.0)],
        [_request()],
        [_window(peak=T0)],
        threshold_pct=50.0,
    )

    assert len(payloads) == 1


def test_coverage_below_threshold_leaves_the_window_alone():
    payloads = cloud_block_payloads_for_windows(
        [_sample(49.9)],
        [_request()],
        [_window(peak=T0)],
        threshold_pct=50.0,
    )

    assert payloads == []


def test_rule_reads_the_nearest_sample_to_culmination():
    samples = [_sample(90.0, time=T0), _sample(10.0, time=T0 + timedelta(hours=1))]

    payloads = cloud_block_payloads_for_windows(
        samples,
        [_request()],
        [_window(peak=T0 + timedelta(minutes=45))],
        threshold_pct=50.0,
    )

    # 45 minutes after T0 is nearer the clear 07:00 sample than the cloudy 06:00 one.
    assert payloads == []


def test_rule_samples_at_peak_time_not_the_midpoint():
    samples = [_sample(90.0, time=T0), _sample(10.0, time=T0 + timedelta(hours=1))]
    window = _window(
        start=T0 - timedelta(minutes=30),
        end=T0 + timedelta(minutes=90),
        peak=T0 + timedelta(minutes=50),
    )

    assert culmination_time(window) == T0 + timedelta(minutes=50)
    payloads = cloud_block_payloads_for_windows(
        samples, [_request()], [window], threshold_pct=50.0
    )

    # The midpoint (T0 + 30 min) sits nearer the cloudy sample, but the
    # peak (T0 + 50 min) sits nearer the clear one.
    assert payloads == []


def test_window_without_a_peak_falls_back_to_the_midpoint():
    window = _window(start=T0, end=T0 + timedelta(minutes=10))

    assert culmination_time(window) == T0 + timedelta(minutes=5)


def test_window_with_no_sample_in_tolerance_is_left_alone():
    payloads = cloud_block_payloads_for_windows(
        [_sample(99.0, time=T0 + timedelta(hours=5))],
        [_request()],
        [_window(peak=T0)],
        threshold_pct=50.0,
        tolerance_s=1800.0,
    )

    assert payloads == []


def test_already_blocked_windows_keep_their_recorded_cause():
    payloads = cloud_block_payloads_for_windows(
        [_sample(99.0)],
        [_request()],
        [_window(peak=T0, valid=False)],
        threshold_pct=50.0,
    )

    assert payloads == []


def test_samples_at_another_target_do_not_leak_across():
    payloads = cloud_block_payloads_for_windows(
        [_sample(99.0, lat=28.61, lon=77.21)],
        [_request()],
        [_window(peak=T0)],
        threshold_pct=50.0,
    )

    assert payloads == []


def test_payloads_come_back_in_window_order():
    late = _window("WIN-OBS-BLR-2", start=T0 + timedelta(hours=1), peak=T0 + timedelta(hours=1))
    early = _window("WIN-OBS-BLR-1", peak=T0)
    samples = [_sample(80.0, time=T0), _sample(80.0, time=T0 + timedelta(hours=1))]

    payloads = cloud_block_payloads_for_windows(
        samples, [_request()], [late, early], threshold_pct=50.0
    )

    assert [payload.window_id for payload in payloads] == [
        "WIN-OBS-BLR-1",
        "WIN-OBS-BLR-2",
    ]


def test_window_naming_an_unknown_request_is_rejected():
    with pytest.raises(ValueError, match="unknown request"):
        cloud_block_payloads_for_windows(
            [_sample(80.0)], [_request()], [_window(request_id="OBS-GHOST")], threshold_pct=50.0
        )


@pytest.mark.parametrize("threshold", [-1.0, 101.0, float("nan"), float("inf")])
def test_bad_threshold_is_rejected(threshold):
    with pytest.raises(ValueError, match="percentage"):
        cloud_block_payloads_for_windows(
            [_sample(80.0)], [_request()], [_window(peak=T0)], threshold_pct=threshold
        )


def test_coverage_at_returns_none_without_a_nearby_sample():
    assert (
        coverage_at(
            [_sample(80.0, time=T0 + timedelta(hours=5))],
            target_lat=BLR[0],
            target_lon=BLR[1],
            moment=T0,
        )
        is None
    )


def test_committed_archive_maps_to_the_expected_blocks():
    archive = load_archive()
    samples = normalize_archive(archive.records)
    blr = _request("OBS-BLR", *BLR)
    delhi = _request("OBS-DEL", 28.61, 77.21)
    peak = datetime(2026, 9, 25, 6, 30, tzinfo=timezone.utc)
    windows = (
        _window("WIN-OBS-BLR-1", "OBS-BLR", start=peak - timedelta(minutes=5), end=peak + timedelta(minutes=5), peak=peak),
        _window("WIN-OBS-DEL-1", "OBS-DEL", start=peak - timedelta(minutes=5), end=peak + timedelta(minutes=5), peak=peak),
    )

    payloads = cloud_block_payloads_for_windows(
        samples, [blr, delhi], windows, threshold_pct=50.0
    )

    # 06:30 ties the 06:00 and 07:00 samples; both Bengaluru samples are
    # cloudy (85/92) while both Delhi samples are clear (15/22).
    assert [(payload.request_id, payload.cloud_cover_pct) for payload in payloads] == [
        ("OBS-BLR", 85.0)
    ]
