"""Command-line entry point: `python -m azimuth_mapper ...`."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from .correction import best_estimate
from .geometry import LatLon, choose_zoom_for_span, destination_point, meters_per_pixel
from .imagery import fetch_snapshot
from .render import AzimuthLine, render_html
from .shadow_detect import detect_shadows
from .solar import solar_position


def _broadcast(values: list | None, count: int, name: str, default, allow_broadcast: bool = True):
    """Align a repeatable flag's values with the --azimuth list.

    Broadcasting a single value to every azimuth only makes sense for flags
    like --distance where "apply this to all of them" is a sane default.
    For per-ray flags like --beamwidth and --label, a lone value would
    silently apply to every azimuth rather than just the one the user meant
    (argparse has no way to associate a flag with a specific --azimuth by
    position), so those require an exact 1:1 count instead.
    """
    if not values:
        return [default] * count
    if allow_broadcast and len(values) == 1:
        return values * count
    if len(values) != count:
        raise SystemExit(
            f"--{name} given {len(values)} time(s) but there are {count} --azimuth values; "
            f"provide exactly one --{name} per --azimuth (use an empty value for 'none')"
        )
    return values


def _parse_beamwidth(raw: str) -> float | None:
    return None if raw.strip().lower() in ("", "none", "-") else float(raw)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Plot azimuth(s) from a GPS point onto a satellite-image snapshot."
    )
    p.add_argument("--lat", type=float, required=True, help="Origin latitude, decimal degrees")
    p.add_argument("--lon", type=float, required=True, help="Origin longitude, decimal degrees")
    p.add_argument(
        "--azimuth",
        type=float,
        action="append",
        required=True,
        help="Compass azimuth in degrees (0=N, 90=E). Repeatable for multiple rays.",
    )
    p.add_argument(
        "--distance",
        type=float,
        action="append",
        help="Ray length in meters (default 1000). One value applies to all, or one per --azimuth.",
    )
    p.add_argument(
        "--beamwidth",
        type=_parse_beamwidth,
        action="append",
        help="Antenna beamwidth in degrees, draws a sector wedge instead of a line. "
        "If given for any azimuth, must be given once per --azimuth, in order "
        '(use "" or "none" for azimuths that should stay a plain line).',
    )
    p.add_argument(
        "--label",
        action="append",
        help="Label per azimuth. If given for any azimuth, must be given once per "
        '--azimuth, in order (use "" for azimuths that should stay unlabeled).',
    )
    p.add_argument(
        "--capture-datetime",
        type=str,
        default=None,
        help="ISO 8601 UTC datetime to assume for the sun-position estimate "
        "(default: current time). E.g. 2026-06-21T12:00:00",
    )
    p.add_argument("--size", type=int, default=640, help="Output image size in pixels (default 640)")
    p.add_argument("--out", type=str, required=True, help="Output HTML file path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    n = len(args.azimuth)
    distances = _broadcast(args.distance, n, "distance", 1000.0)
    beamwidths = _broadcast(args.beamwidth, n, "beamwidth", None, allow_broadcast=False)
    labels = _broadcast(args.label, n, "label", None, allow_broadcast=False)
    labels = [label or None for label in labels]

    origin = LatLon(args.lat, args.lon)
    capture_dt = (
        datetime.fromisoformat(args.capture_datetime).replace(tzinfo=timezone.utc)
        if args.capture_datetime
        else datetime.now(timezone.utc)
    )

    max_distance = max(distances)
    zoom = choose_zoom_for_span(max_distance, args.lat, target_px=args.size)
    snapshot = fetch_snapshot(origin, zoom, size_px=args.size)
    mpp = meters_per_pixel(args.lat, zoom)
    origin_px = (args.size / 2, args.size / 2)

    lines = [
        AzimuthLine(azimuth_deg=az, distance_m=dist, label=label, beamwidth_deg=bw)
        for az, dist, label, bw in zip(args.azimuth, distances, labels, beamwidths)
    ]

    sun = solar_position(args.lat, args.lon, capture_dt)
    shadow_observations = detect_shadows(snapshot.image, origin_px)
    shadow_estimate = best_estimate(shadow_observations, sun, mpp)

    html = render_html(
        snapshot,
        origin_px,
        origin,
        lines,
        mpp,
        sun=sun,
        sun_datetime=capture_dt,
        shadow_estimate=shadow_estimate,
    )
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {args.out}")
    print(f"Origin: {origin.lat:.6f}, {origin.lon:.6f}  (zoom {zoom}, {mpp:.2f} m/px)")
    for line in lines:
        dest = destination_point(origin, line.azimuth_deg, line.distance_m)
        print(f"  azimuth {line.azimuth_deg:.1f}° x {line.distance_m:.0f} m -> {dest.lat:.6f}, {dest.lon:.6f}")
    if shadow_estimate is not None:
        height = (
            f"{shadow_estimate.reference_height_m:.1f} m"
            if shadow_estimate.reference_height_m is not None
            else "n/a"
        )
        print(
            f"Shadow estimate: length {shadow_estimate.shadow_length_m:.1f} m, "
            f"height ~{height} ({shadow_estimate.confidence} confidence)"
        )
    else:
        print("Shadow estimate: none found near origin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
