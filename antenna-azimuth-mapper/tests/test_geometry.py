from datetime import datetime, timezone

import pytest

from azimuth_mapper.geometry import (
    LatLon,
    bearing_between,
    choose_zoom_for_span,
    destination_point,
    haversine_distance_m,
    meters_per_pixel,
)
from azimuth_mapper.solar import solar_position

PRAGUE = LatLon(50.0755, 14.4378)


@pytest.mark.parametrize("azimuth,distance_m", [(0, 5000), (45, 10000), (123.5, 3000), (270, 8000)])
def test_destination_and_bearing_roundtrip(azimuth, distance_m):
    dest = destination_point(PRAGUE, azimuth, distance_m)

    measured_bearing = bearing_between(PRAGUE, dest)
    assert measured_bearing == pytest.approx(azimuth % 360, abs=0.5)

    measured_distance = haversine_distance_m(PRAGUE, dest)
    assert measured_distance == pytest.approx(distance_m, rel=0.01)


def test_meters_per_pixel_in_sane_range():
    # Standard Web Mercator ground resolution at the equator, zoom 15, is ~4.8 m/px.
    value = meters_per_pixel(0.0, 15)
    assert 3.0 < value < 6.0

    # Resolution should get coarser at higher latitude for the same zoom.
    assert meters_per_pixel(60.0, 15) < meters_per_pixel(0.0, 15)


def test_choose_zoom_for_span_covers_requested_distance():
    distance_m = 2000
    zoom = choose_zoom_for_span(distance_m, PRAGUE.lat, target_px=640)
    span_m = meters_per_pixel(PRAGUE.lat, zoom) * 640
    assert span_m >= 2 * distance_m
    # One zoom level higher should be too tight (or already at the max we try).
    if zoom < 19:
        tighter_span = meters_per_pixel(PRAGUE.lat, zoom + 1) * 640
        assert tighter_span < 2 * distance_m


def test_solar_position_basic_bounds():
    dt = datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    pos = solar_position(PRAGUE.lat, PRAGUE.lon, dt)
    assert -90 <= pos.elevation_deg <= 90
    assert 0 <= pos.azimuth_deg < 360
    # Summer solstice, local solar noon in central Europe: sun should be
    # high and roughly southward, not northward.
    assert pos.elevation_deg > 50
    assert 100 < pos.azimuth_deg < 260


def test_solar_position_moves_east_to_west_over_the_day():
    day = datetime(2026, 3, 20, tzinfo=timezone.utc)
    morning = solar_position(PRAGUE.lat, PRAGUE.lon, day.replace(hour=7))
    afternoon = solar_position(PRAGUE.lat, PRAGUE.lon, day.replace(hour=16))
    # Sun azimuth increases (clockwise, roughly E -> S -> W) through the day.
    assert morning.azimuth_deg < afternoon.azimuth_deg
