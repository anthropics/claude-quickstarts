"""Fetch and stitch Esri World Imagery tiles around a point.

Esri's World Imagery basemap is used because it needs no API key. It is a
mosaic assembled from many source images of different dates and viewing
angles, which is exactly why the shadow-based estimate in correction.py has
to stay a heuristic: there is no single, known capture geometry for a tile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO

import requests
from PIL import Image

from .geometry import TILE_SIZE_PX, LatLon, lonlat_to_global_pixel

TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
REQUEST_TIMEOUT_S = 15


@dataclass(frozen=True)
class MapSnapshot:
    image: Image.Image
    center: LatLon
    zoom: int
    origin_px: tuple[float, float]  # global Web Mercator pixel coords of the image's top-left corner


def fetch_snapshot(center: LatLon, zoom: int, size_px: int = 640) -> MapSnapshot:
    """Fetch just enough Esri World Imagery tiles to cover a size_px square centered on center."""
    center_x, center_y = lonlat_to_global_pixel(center, zoom)
    half = size_px / 2

    left, top = center_x - half, center_y - half
    right, bottom = center_x + half, center_y + half

    first_tile_x, first_tile_y = math.floor(left / TILE_SIZE_PX), math.floor(top / TILE_SIZE_PX)
    last_tile_x, last_tile_y = math.floor((right - 1) / TILE_SIZE_PX), math.floor(
        (bottom - 1) / TILE_SIZE_PX
    )
    n_tiles = 2**zoom

    mosaic_w = (last_tile_x - first_tile_x + 1) * TILE_SIZE_PX
    mosaic_h = (last_tile_y - first_tile_y + 1) * TILE_SIZE_PX
    mosaic = Image.new("RGB", (mosaic_w, mosaic_h))

    session = requests.Session()
    for ty in range(first_tile_y, last_tile_y + 1):
        for tx in range(first_tile_x, last_tile_x + 1):
            wrapped_x = tx % n_tiles
            url = TILE_URL.format(z=zoom, y=ty, x=wrapped_x)
            resp = session.get(url, timeout=REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            tile = Image.open(BytesIO(resp.content)).convert("RGB")
            mosaic.paste(
                tile, ((tx - first_tile_x) * TILE_SIZE_PX, (ty - first_tile_y) * TILE_SIZE_PX)
            )

    mosaic_origin_x = first_tile_x * TILE_SIZE_PX
    mosaic_origin_y = first_tile_y * TILE_SIZE_PX
    crop_left = int(round(left - mosaic_origin_x))
    crop_top = int(round(top - mosaic_origin_y))
    cropped = mosaic.crop((crop_left, crop_top, crop_left + size_px, crop_top + size_px))

    return MapSnapshot(
        image=cropped,
        center=center,
        zoom=zoom,
        origin_px=(mosaic_origin_x + crop_left, mosaic_origin_y + crop_top),
    )
