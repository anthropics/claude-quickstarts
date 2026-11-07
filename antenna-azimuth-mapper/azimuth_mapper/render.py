"""Render a satellite-image snapshot + SVG azimuth overlay as self-contained HTML.

The image is embedded as a base64 data: URI and every asset is inlined (the
only external request is the Google Fonts stylesheet), so the output has no
external network dependency at view time — it works both as a plain HTML
file and when published through the Claude `Artifact` tool, whose CSP blocks
live calls to tile servers. The markup is a fragment (no <!DOCTYPE>/<html>/
<head>/<body>) so it can be dropped straight into an Artifact's own page
skeleton; browsers render it fine standalone too.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Optional

from .correction import ShadowEstimate
from .geometry import LatLon
from .imagery import MapSnapshot
from .solar import SolarPosition


@dataclass(frozen=True)
class AzimuthLine:
    azimuth_deg: float
    distance_m: float
    label: str | None = None
    beamwidth_deg: float | None = None  # draws a sector wedge instead of a single ray


# Categorical ray colors: chosen for contrast against satellite imagery in
# both themes, independent of the page-chrome palette below.
_RAY_COLORS = ["#ff6a3d", "#3ea1ff", "#ffd23f", "#3ddc84", "#c792ff"]


def _polar_offset_px(azimuth_deg: float, radius_px: float) -> tuple[float, float]:
    rad = math.radians(azimuth_deg)
    return radius_px * math.sin(rad), -radius_px * math.cos(rad)


def _wedge_path(origin_px: tuple[float, float], azimuth_deg: float, beamwidth_deg: float, radius_px: float) -> str:
    ox, oy = origin_px
    start = azimuth_deg - beamwidth_deg / 2
    end = azimuth_deg + beamwidth_deg / 2
    points = [(ox, oy)]
    steps = max(2, int(abs(beamwidth_deg) / 2))
    for i in range(steps + 1):
        az = start + (end - start) * i / steps
        dx, dy = _polar_offset_px(az, radius_px)
        points.append((ox + dx, oy + dy))
    points.append((ox, oy))
    return "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(
    snapshot: MapSnapshot,
    origin_px: tuple[float, float],
    origin_latlon: LatLon,
    lines: list[AzimuthLine],
    meters_per_pixel: float,
    sun: Optional[SolarPosition] = None,
    sun_datetime: Optional[datetime] = None,
    shadow_estimate: Optional[ShadowEstimate] = None,
) -> str:
    size = snapshot.image.size[0]
    buf = BytesIO()
    snapshot.image.save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    ox, oy = origin_px
    svg_parts: list[str] = []
    ray_chips: list[str] = []

    for i, line in enumerate(lines):
        color = _RAY_COLORS[i % len(_RAY_COLORS)]
        radius_px = line.distance_m / meters_per_pixel
        if line.beamwidth_deg:
            path = _wedge_path((ox, oy), line.azimuth_deg, line.beamwidth_deg, radius_px)
            svg_parts.append(
                f'<path d="{path}" fill="{color}" fill-opacity="0.22" '
                f'stroke="{color}" stroke-width="2"/>'
            )
        else:
            dx, dy = _polar_offset_px(line.azimuth_deg, radius_px)
            svg_parts.append(
                f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{ox + dx:.1f}" y2="{oy + dy:.1f}" '
                f'stroke="{color}" stroke-width="3" stroke-linecap="round"/>'
            )
            svg_parts.append(f'<circle cx="{ox + dx:.1f}" cy="{oy + dy:.1f}" r="4" fill="{color}"/>')

        label = line.label or f"{line.azimuth_deg:.1f}°"
        lx, ly = _polar_offset_px(line.azimuth_deg, radius_px * 0.55)
        svg_parts.append(
            f'<text x="{ox + lx:.1f}" y="{oy + ly:.1f}" fill="{color}" font-size="13" '
            f'font-family="\'IBM Plex Mono\',ui-monospace,monospace" font-weight="600" '
            f'paint-order="stroke" stroke="#0009" stroke-width="3">{_escape(label)}</text>'
        )

        chip_value = f"{line.azimuth_deg:05.1f}°"
        if line.beamwidth_deg:
            chip_value += f" ±{line.beamwidth_deg:.0f}°"
        chip_value += f" · {_format_distance(line.distance_m)}"
        ray_chips.append(
            f'<div class="ray-chip" style="--chip-color:{color}">'
            f'<span class="ray-chip__swatch"></span>'
            f'<span class="ray-chip__label">{_escape(label)}</span>'
            f'<span class="ray-chip__value">{_escape(chip_value)}</span>'
            f"</div>"
        )

    if shadow_estimate is not None:
        cx, cy = shadow_estimate.centroid_px
        svg_parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="none" '
            f'stroke="#ffffff" stroke-width="2" stroke-dasharray="3,3"/>'
        )

    svg_parts.append(
        f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="6" fill="#ffffff" stroke="#111" stroke-width="2"/>'
    )

    # Compass rose (top-right)
    rose_cx, rose_cy, rose_r = size - 46, 46, 26
    svg_parts.append(
        f'<circle cx="{rose_cx}" cy="{rose_cy}" r="{rose_r}" fill="#0007" stroke="#fff" stroke-width="1.5"/>'
        f'<line x1="{rose_cx}" y1="{rose_cy + rose_r - 4}" x2="{rose_cx}" y2="{rose_cy - rose_r + 4}" '
        f'stroke="#fff" stroke-width="2"/>'
        f'<text x="{rose_cx}" y="{rose_cy - rose_r + 2}" fill="#fff" font-size="13" '
        f'font-family="\'IBM Plex Sans\',ui-sans-serif,sans-serif" font-weight="700" text-anchor="middle">N</text>'
    )

    # Scale bar (bottom-left)
    bar_m = _nice_scale_length(size * 0.25 * meters_per_pixel)
    bar_px = bar_m / meters_per_pixel
    bar_x, bar_y = 16, size - 22
    svg_parts.append(
        f'<line x1="{bar_x}" y1="{bar_y}" x2="{bar_x + bar_px:.1f}" y2="{bar_y}" stroke="#fff" stroke-width="3"/>'
        f'<line x1="{bar_x}" y1="{bar_y - 5}" x2="{bar_x}" y2="{bar_y + 5}" stroke="#fff" stroke-width="3"/>'
        f'<line x1="{bar_x + bar_px:.1f}" y1="{bar_y - 5}" x2="{bar_x + bar_px:.1f}" y2="{bar_y + 5}" stroke="#fff" stroke-width="3"/>'
        f'<text x="{bar_x}" y="{bar_y - 8}" fill="#fff" font-size="12" '
        f'font-family="\'IBM Plex Mono\',ui-monospace,monospace" paint-order="stroke" stroke="#0009" stroke-width="3">'
        f'{_format_distance(bar_m)}</text>'
    )

    sun_row = ""
    if sun is not None and sun_datetime is not None:
        sun_row = (
            '<div class="readout-row">'
            '<span class="readout-row__key">Sun</span>'
            f'<span class="readout-row__value">az {sun.azimuth_deg:05.1f}° · '
            f"elev {sun.elevation_deg:+.1f}° · "
            f'{sun_datetime.strftime("%Y-%m-%d %H:%M")} UTC (assumed)</span>'
            "</div>"
        )

    if shadow_estimate is not None:
        height_txt = (
            f"{shadow_estimate.reference_height_m:.1f} m"
            if shadow_estimate.reference_height_m is not None
            else "n/a — sun too low"
        )
        shadow_block = (
            '<div class="shadow-card">'
            f'<span class="pill pill--{shadow_estimate.confidence}">{shadow_estimate.confidence} confidence</span>'
            f'<span class="shadow-card__text">shadow {_format_distance(shadow_estimate.shadow_length_m)} '
            f"⇒ reference object ≈ {height_txt} "
            f"({shadow_estimate.angular_error_deg:.0f}° off the expected sun-shadow direction)</span>"
            "</div>"
        )
    else:
        shadow_block = (
            '<div class="shadow-card shadow-card--empty">'
            '<span class="pill pill--none">no shadow</span>'
            '<span class="shadow-card__text">No usable shadow detected near the origin — '
            "no reference height measured here.</span>"
            "</div>"
        )

    ray_chips_html = "".join(ray_chips) or '<div class="ray-chip ray-chip--empty">no azimuths</div>'

    return f"""<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #f1efe6;
    --surface: #fffdf8;
    --ink: #221e17;
    --ink-muted: #776d59;
    --accent: #c9501c;
    --accent-ink: #fff8f2;
    --line: #ddd5c1;
    --shadow: 0 1px 2px rgba(34,30,23,0.06), 0 8px 24px rgba(34,30,23,0.08);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #16130e;
      --surface: #1f1b14;
      --ink: #f2ecdd;
      --ink-muted: #a89a80;
      --accent: #ff8a4b;
      --accent-ink: #201200;
      --line: #37301f;
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 10px 30px rgba(0,0,0,0.35);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #16130e;
    --surface: #1f1b14;
    --ink: #f2ecdd;
    --ink-muted: #a89a80;
    --accent: #ff8a4b;
    --accent-ink: #201200;
    --line: #37301f;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 10px 30px rgba(0,0,0,0.35);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: 'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif;
    display: flex;
    justify-content: center;
    padding: 28px 16px;
  }}
  .panel {{
    width: 100%;
    max-width: {size}px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    box-shadow: var(--shadow);
    overflow: hidden;
  }}
  .panel__head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--line);
  }}
  .panel__title {{
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--accent);
  }}
  .panel__origin {{
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 13px;
    color: var(--ink-muted);
  }}
  .viewport {{ position: relative; width: 100%; line-height: 0; background: #000; }}
  .viewport svg {{ display: block; width: 100%; height: auto; }}
  .readout {{ padding: 16px 18px 18px; display: flex; flex-direction: column; gap: 12px; }}
  .readout__rays {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .ray-chip {{
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 6px 10px;
    border: 1px solid var(--line);
    border-radius: 999px;
    font-size: 12.5px;
  }}
  .ray-chip__swatch {{
    width: 9px; height: 9px; border-radius: 50%;
    background: var(--chip-color, var(--accent));
    flex: none;
  }}
  .ray-chip__label {{ font-weight: 600; }}
  .ray-chip__value {{
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
    color: var(--ink-muted);
  }}
  .readout-row {{ display: flex; gap: 8px; font-size: 13px; align-items: baseline; }}
  .readout-row__key {{
    text-transform: uppercase; letter-spacing: 0.05em; font-size: 11px;
    color: var(--ink-muted); flex: none; width: 42px;
  }}
  .readout-row__value {{
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
  }}
  .shadow-card {{
    display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
    padding: 10px 12px; border-radius: 10px; background: var(--bg); border: 1px solid var(--line);
    font-size: 12.5px; color: var(--ink-muted);
  }}
  .pill {{
    flex: none; padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.03em;
  }}
  .pill--high {{ background: var(--accent); color: var(--accent-ink); }}
  .pill--medium {{ background: transparent; border: 1px solid var(--accent); color: var(--accent); }}
  .pill--low, .pill--none {{ background: transparent; border: 1px solid var(--line); color: var(--ink-muted); }}
  .note {{ margin: 2px 0 0; font-size: 11.5px; line-height: 1.5; color: var(--ink-muted); }}
</style>
<div class="panel">
  <div class="panel__head">
    <span class="panel__title">Azimuth Mapper</span>
    <span class="panel__origin">{origin_latlon.lat:.6f}, {origin_latlon.lon:.6f}</span>
  </div>
  <div class="viewport">
    <svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
      <image href="{data_uri}" x="0" y="0" width="{size}" height="{size}"/>
      {''.join(svg_parts)}
    </svg>
  </div>
  <div class="readout">
    <div class="readout__rays">{ray_chips_html}</div>
    {sun_row}
    {shadow_block}
    <p class="note">Shadow-based estimate is a heuristic from image shadows + true sun position, not a metadata-verified correction — public satellite basemaps do not expose the sensor's viewing angle. See README &ldquo;Accuracy &amp; limitations&rdquo;.</p>
  </div>
</div>
"""


def _nice_scale_length(raw_m: float) -> float:
    if raw_m <= 0:
        return 10.0
    magnitude = 10 ** math.floor(math.log10(raw_m))
    for mult in (1, 2, 5, 10):
        candidate = magnitude * mult
        if candidate >= raw_m:
            return candidate
    return magnitude * 10


def _format_distance(meters: float) -> str:
    return f"{meters / 1000:.1f} km" if meters >= 1000 else f"{meters:.0f} m"
