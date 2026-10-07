"""Low-precision solar position (Michalsky/NOAA-style), no external dependencies.

Accurate to roughly 0.01 deg for 1950-2050, which is far more than this tool
needs: it is only used to sanity-check a shadow direction detected in an
image, not for anything safety-critical.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SolarPosition:
    azimuth_deg: float  # compass bearing of the sun, 0 = north, clockwise
    elevation_deg: float  # angle above the horizon


def _julian_day(dt_utc: datetime) -> float:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    dt_utc = dt_utc.astimezone(timezone.utc)
    epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # JD 2451545.0
    return 2451545.0 + (dt_utc - epoch).total_seconds() / 86400.0


def solar_position(lat_deg: float, lon_deg: float, dt_utc: datetime) -> SolarPosition:
    """Sun azimuth/elevation as seen from (lat, lon) at the given UTC instant."""
    jd = _julian_day(dt_utc)
    n = jd - 2451545.0

    mean_lon = math.radians((280.460 + 0.9856474 * n) % 360)
    mean_anomaly = math.radians((357.528 + 0.9856003 * n) % 360)
    ecliptic_lon = mean_lon + math.radians(
        1.915 * math.sin(mean_anomaly) + 0.020 * math.sin(2 * mean_anomaly)
    )
    obliquity = math.radians(23.439 - 0.0000004 * n)

    right_ascension = math.atan2(
        math.cos(obliquity) * math.sin(ecliptic_lon), math.cos(ecliptic_lon)
    )
    declination = math.asin(math.sin(obliquity) * math.sin(ecliptic_lon))

    gmst_deg = (280.46061837 + 360.98564736629 * n) % 360
    hour_angle_deg = (gmst_deg + lon_deg - math.degrees(right_ascension)) % 360
    if hour_angle_deg > 180:
        hour_angle_deg -= 360
    hour_angle = math.radians(hour_angle_deg)

    lat = math.radians(lat_deg)
    sin_elevation = math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(
        declination
    ) * math.cos(hour_angle)
    sin_elevation = max(-1.0, min(1.0, sin_elevation))
    elevation = math.asin(sin_elevation)

    cos_azimuth = (math.sin(declination) - math.sin(lat) * sin_elevation) / (
        math.cos(lat) * math.cos(elevation)
    ) if abs(math.cos(lat) * math.cos(elevation)) > 1e-9 else 0.0
    cos_azimuth = max(-1.0, min(1.0, cos_azimuth))
    azimuth = math.acos(cos_azimuth)
    azimuth_deg = math.degrees(azimuth)
    if math.sin(hour_angle) > 0:
        azimuth_deg = 360 - azimuth_deg

    return SolarPosition(azimuth_deg=azimuth_deg % 360, elevation_deg=math.degrees(elevation))
