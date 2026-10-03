# Antenna Azimuth Mapper

A small command-line tool — and a Cowork/Claude Code skill built on top of
it — that plots one or more compass azimuths (e.g. for aiming a directional
antenna) from a GPS point onto a satellite-image snapshot, and measures a
reference object's height from its shadow — the quantity needed to calibrate
how far this imagery leans.

There is no live GPS sensor in a Claude/Cowork session, so coordinates are
supplied by the user (e.g. pasted from a phone's maps app "share location"
feature) rather than read from a device.

## Setup

```bash
cd antenna-azimuth-mapper
pip install -r requirements.txt
```

No API key is required — imagery comes from Esri's public World Imagery
basemap.

## Usage

```bash
python -m azimuth_mapper.cli \
  --lat 50.0755 --lon 14.4378 \
  --azimuth 45 --distance 2000 --label "Site A" \
  --azimuth 120 --distance 1500 --beamwidth 30 --label "Sector 2" \
  --out map.html
```

- `--azimuth` is repeatable — one ray (or sector wedge, with `--beamwidth`)
  per value.
- `--distance` accepts one value applied to every azimuth, or one value per
  `--azimuth`, in meters (default 1000 m).
- `--beamwidth` (degrees) draws a sector wedge instead of a single ray —
  useful for planning a directional/sector antenna's coverage cone. Unlike
  `--distance`, it does **not** broadcast: if you use it at all with more
  than one `--azimuth`, pass exactly one `--beamwidth` per `--azimuth`, in
  the same order, using `""` or `none` for the rays that should stay plain
  lines — e.g. `--azimuth 45 --beamwidth "" --azimuth 120 --beamwidth 30`.
  `--label` works the same way when used with multiple azimuths.
- `--capture-datetime` (ISO 8601 UTC, e.g. `2026-06-21T12:00:00`) sets the
  date/time assumed for the sun-position calculation used in the shadow
  estimate. Defaults to the current time, since the actual capture date of
  a public satellite basemap tile isn't published.
- Open the resulting HTML file in a browser, or hand it to the `Artifact`
  tool from a Claude session to publish it inline.

Run the tests with:

```bash
python -m pytest
```

## Accuracy & limitations

**The azimuth ray itself is exact geodesic math** (forward geodesic from the
given origin), independent of the imagery.

**The shadow-based estimate is a heuristic, not a certified measurement.**
Rigorous photogrammetric correction of satellite imagery (relief
displacement / collinearity) needs the sensor's exterior orientation for
the exact image used — its viewing (off-nadir) angle and azimuth at capture
time. Public satellite basemaps (Esri World Imagery, Mapbox, Google) are
mosaics of tiles from different source images and different dates, and none
of that per-tile geometry is exposed through their tile APIs. This tool
does **not** invent that number.

What it does instead, and what it reports:

1. Detects elongated dark blobs near the origin point in the fetched image
   (`shadow_detect.py` — an OpenCV threshold + contour heuristic).
2. Computes the astronomically-true sun azimuth/elevation for the given
   location and the assumed capture date/time (`solar.py` — a standard
   low-precision solar position formula, no external data needed).
3. If a detected blob's orientation is close to the sun-opposite direction
   expected for a real shadow, it reports the shadow's length and, from
   classic shadow trigonometry (`length * tan(sun elevation)`), an
   **estimated height** of whatever cast it — flagged with a confidence
   level and how many degrees off the expected shadow direction it was.

That height is genuinely computed from the image and true solar geometry,
but it is approximate: the assumed capture date/time may be wrong (basemap
imagery is typically weeks to years old), the detected blob might not be the
object you meant, and low sun elevation makes the length-to-height
conversion noisy. Entering a known height by hand is more reliable when you
have one.

**Why the height matters.** A shadow alone cannot tell you which way a tall
object leans in the image — that needs the satellite's viewing azimuth,
which no public basemap publishes per tile. But a shadow and a lean are the
same radial geometry with the sun swapped for the satellite, so once the
height is known, *measuring* the object's lean yields the viewing geometry,
and from there any elevated target's bearing can be corrected. This CLI
supplies the height half; the web app in
[`../antenna-azimuth-webapp`](../antenna-azimuth-webapp) pairs it with a
marked base and top to do the correction interactively.

## Layout

- `azimuth_mapper/geometry.py` — geodesic math (destination point, bearing,
  distance) and Web Mercator tile/pixel math.
- `azimuth_mapper/solar.py` — sun azimuth/elevation for a place and UTC time.
- `azimuth_mapper/imagery.py` — fetches and stitches Esri World Imagery
  tiles around a point.
- `azimuth_mapper/shadow_detect.py` — finds candidate shadow blobs.
- `azimuth_mapper/correction.py` — turns a shadow + sun position into a
  bounded height estimate (see limitations above).
- `azimuth_mapper/render.py` — builds the self-contained HTML output (image
  embedded as a data URI, azimuth rays/wedges and legend as inline SVG).
- `azimuth_mapper/cli.py` — command-line entry point.
- `.claude/skills/azimuth-satellite/SKILL.md` — the Cowork/Claude Code
  skill that drives this conversationally.
