"""Heuristic shadow-blob detection in a satellite snapshot.

This is deliberately simple: threshold the darkest pixels, keep the
elongated blobs, and describe each one's orientation and length. It has no
ground truth to check itself against (no per-tile capture metadata exists
for public satellite basemaps — see imagery.py), so it is a signal to feed
into correction.py's estimate, not a precise measurement.

A blob's principal axis is ambiguous by 180 degrees (PCA doesn't know which
end is the object and which is the shadow tip); correction.py resolves that
using the independently-computed true sun position.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

MIN_CONTOUR_AREA_PX = 25
MIN_ELONGATION = 2.0  # major axis / minor axis, to reject blobs that aren't shadow-shaped


@dataclass(frozen=True)
class ShadowObservation:
    centroid_px: tuple[float, float]
    axis_deg_a: float  # one of the two 180-degree-apart candidate directions, compass bearing
    axis_deg_b: float
    length_px: float
    area_px: float
    distance_from_origin_px: float


def _contour_orientation_deg(contour: np.ndarray) -> tuple[float, float]:
    """Principal-axis compass bearing (both 180-degree-apart candidates) via PCA."""
    points = contour.reshape(-1, 2).astype(np.float64)
    mean, eigenvectors, _ = cv2.PCACompute2(points, mean=None)
    vx, vy = eigenvectors[0]
    # Image space: x right, y down. Compass bearing: 0 = up (north), clockwise.
    angle_deg = (np.degrees(np.arctan2(vx, -vy))) % 360
    return angle_deg, (angle_deg + 180) % 360


def detect_shadows(image: Image.Image, origin_px: tuple[float, float]) -> list[ShadowObservation]:
    """Find candidate shadow blobs, sorted by proximity to origin_px (nearest first)."""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    observations: list[ShadowObservation] = []
    ox, oy = origin_px
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_CONTOUR_AREA_PX or len(contour) < 5:
            continue

        rect = cv2.minAreaRect(contour)
        (cx, cy), (w, h), _ = rect
        major, minor = max(w, h), max(min(w, h), 1e-6)
        if major / minor < MIN_ELONGATION:
            continue

        axis_a, axis_b = _contour_orientation_deg(contour)
        distance = float(np.hypot(cx - ox, cy - oy))
        observations.append(
            ShadowObservation(
                centroid_px=(cx, cy),
                axis_deg_a=axis_a,
                axis_deg_b=axis_b,
                length_px=major,
                area_px=area,
                distance_from_origin_px=distance,
            )
        )

    observations.sort(key=lambda obs: obs.distance_from_origin_px)
    return observations
