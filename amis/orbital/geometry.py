"""Spherical field-of-regard conversion used by the pass search."""

from math import asin, cos, degrees, pi, radians, sin

EARTH_RADIUS_KM = 6378.137
MU_KM3_S2 = 398600.4418


def mean_altitude_km(mean_motion_rev_day: float) -> float:
    angular_rate = mean_motion_rev_day * 2 * pi / 86400
    return (MU_KM3_S2 / angular_rate**2) ** (1 / 3) - EARTH_RADIUS_KM


def target_elevation_threshold(off_nadir_deg: float, altitude_km: float) -> float:
    ratio = (EARTH_RADIUS_KM + altitude_km) / EARTH_RADIUS_KM * sin(radians(off_nadir_deg))
    if ratio >= 1:
        return 0.0
    return 90 - degrees(asin(ratio))


def off_nadir_angle(elevation_deg: float, altitude_km: float) -> float:
    return degrees(asin(EARTH_RADIUS_KM / (EARTH_RADIUS_KM + altitude_km) * cos(radians(elevation_deg))))
