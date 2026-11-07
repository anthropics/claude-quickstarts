"""Turn a detected shadow + the true sun position into a reference height.

Shadow length in the image, combined with the astronomically-true sun
elevation for the place/time, gives the height of the object that cast it
(classic shadow-length trigonometry). That height is the input needed to
calibrate how far this imagery leans — see the README's "What is and isn't
distorted" section — not a statement about obstructions on a path.

A shadow alone does *not* give the satellite's viewing azimuth: that needs
the object's observed lean as well. The web app pairs the two; this module
supplies the height half.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .shadow_detect import ShadowObservation
from .solar import SolarPosition

MIN_SUN_ELEVATION_FOR_HEIGHT_DEG = 5.0
MAX_AXIS_ANGULAR_ERROR_DEG = 45.0


@dataclass(frozen=True)
class ShadowEstimate:
    shadow_azimuth_deg: float  # resolved direction, object base -> shadow tip
    angular_error_deg: float  # distance from the astronomically-expected shadow direction
    shadow_length_m: float
    reference_height_m: float | None
    confidence: str  # "low" | "medium" | "high"
    centroid_px: tuple[float, float]


def _angular_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def estimate_from_shadow(
    obs: ShadowObservation, sun: SolarPosition, meters_per_px: float
) -> ShadowEstimate | None:
    """None means the blob doesn't look like a solar shadow at this sun position."""
    expected_shadow_azimuth = (sun.azimuth_deg + 180) % 360
    err_a = _angular_diff(obs.axis_deg_a, expected_shadow_azimuth)
    err_b = _angular_diff(obs.axis_deg_b, expected_shadow_azimuth)
    shadow_azimuth, angular_error = (
        (obs.axis_deg_a, err_a) if err_a <= err_b else (obs.axis_deg_b, err_b)
    )

    if sun.elevation_deg <= 0 or angular_error > MAX_AXIS_ANGULAR_ERROR_DEG:
        return None

    shadow_length_m = obs.length_px * meters_per_px
    height = None
    if sun.elevation_deg > MIN_SUN_ELEVATION_FOR_HEIGHT_DEG:
        height = shadow_length_m * math.tan(math.radians(sun.elevation_deg))

    if angular_error < 10 and obs.area_px > 60:
        confidence = "high"
    elif angular_error < 25:
        confidence = "medium"
    else:
        confidence = "low"

    return ShadowEstimate(
        shadow_azimuth_deg=shadow_azimuth,
        angular_error_deg=angular_error,
        shadow_length_m=shadow_length_m,
        reference_height_m=height,
        confidence=confidence,
        centroid_px=obs.centroid_px,
    )


def best_estimate(
    observations: list[ShadowObservation], sun: SolarPosition, meters_per_px: float
) -> ShadowEstimate | None:
    """Nearest-to-origin candidate first; return the first one that looks like a real shadow."""
    for obs in observations:
        estimate = estimate_from_shadow(obs, sun, meters_per_px)
        if estimate is not None:
            return estimate
    return None
