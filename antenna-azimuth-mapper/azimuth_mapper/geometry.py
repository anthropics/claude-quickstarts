"""Geodesic and Web Mercator math shared by the rest of the package."""

from __future__ import annotations

import math
from dataclasses import dataclass

WGS84_RADIUS_M = 6371008.8  # mean earth radius, good enough for tens-of-km spans
TILE_SIZE_PX = 256


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float


def destination_point(origin: LatLon, azimuth_deg: float, distance_m: float) -> LatLon:
    """Forward geodesic: point reached from origin along azimuth_deg for distance_m."""
    lat1 = math.radians(origin.lat)
    lon1 = math.radians(origin.lon)
    brng = math.radians(azimuth_deg % 360)
    delta = distance_m / WGS84_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(delta) + math.cos(lat1) * math.sin(delta) * math.cos(brng)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brng) * math.sin(delta) * math.cos(lat1),
        math.cos(delta) - math.sin(lat1) * math.sin(lat2),
    )
    return LatLon(math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)


def bearing_between(a: LatLon, b: LatLon) -> float:
    """Initial compass bearing in degrees from point a to point b."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


def haversine_distance_m(a: LatLon, b: LatLon) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * WGS84_RADIUS_M * math.asin(math.sqrt(h))


def meters_per_pixel(lat: float, zoom: int) -> float:
    """Ground resolution of a Web Mercator tile at the given latitude/zoom."""
    return (math.cos(math.radians(lat)) * 2 * math.pi * WGS84_RADIUS_M) / (
        TILE_SIZE_PX * 2**zoom
    )


def lonlat_to_global_pixel(point: LatLon, zoom: int) -> tuple[float, float]:
    """Web Mercator pixel coordinates at the given zoom, in the global tile pixel space."""
    lat_rad = math.radians(point.lat)
    n = 2**zoom
    x = (point.lon + 180.0) / 360.0 * n * TILE_SIZE_PX
    y = (
        (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
        * TILE_SIZE_PX
    )
    return x, y


def global_pixel_to_lonlat(x: float, y: float, zoom: int) -> LatLon:
    n = 2**zoom
    lon = x / (n * TILE_SIZE_PX) * 360.0 - 180.0
    y_norm = 1.0 - 2.0 * y / (n * TILE_SIZE_PX)
    lat_rad = math.atan(math.sinh(math.pi * y_norm))
    return LatLon(math.degrees(lat_rad), lon)


def choose_zoom_for_span(distance_m: float, lat: float, target_px: int = 640) -> int:
    """Pick the smallest zoom whose ground span at least covers 2x the max distance."""
    for zoom in range(19, 0, -1):
        span_m = meters_per_pixel(lat, zoom) * target_px
        if span_m >= 2 * distance_m:
            return zoom
    return 1
