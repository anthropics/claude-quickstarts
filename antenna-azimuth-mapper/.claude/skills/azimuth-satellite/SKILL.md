---
name: azimuth-satellite
description: Plot a compass azimuth (e.g. for aiming a directional antenna) from a GPS point onto a satellite-image snapshot, and measure a reference object's height from its shadow — the input that calibrates the imagery's viewing angle.
---

# Azimuth satellite mapper

Walk the user through plotting one or more azimuths from a GPS position
onto a satellite-image snapshot, then publish the result as an Artifact.
Be conversational — this tool has no device GPS or compass, so every input
comes from the user.

## 0. Orient

Briefly explain what's about to happen: you'll ask for their position and
the azimuth(s) they want plotted, run the mapper, and show them the
resulting satellite snapshot with the azimuth line(s) drawn on it — plus,
if a usable shadow is visible near their position, a rough height estimate
of whatever cast it. That height is what calibrates how far this imagery
leans, which is what makes a bearing to an elevated target trustworthy.
Mention up front that the shadow measurement is a heuristic, not a
survey-grade measurement — see this project's `README.md` "Accuracy &
limitations" section if they want the details.

## 1. Environment check

Confirm dependencies are installed:
`python -c "import cv2, numpy, PIL, requests; print('ok')"` run from the
`antenna-azimuth-mapper/` directory. If it fails:
`pip install -r antenna-azimuth-mapper/requirements.txt`.

No API key is needed — imagery comes from Esri's public World Imagery
basemap.

## 2. Gather inputs

Ask the user for, conversationally (don't demand all at once if they'd
rather go back and forth):

- **Their GPS position** (latitude/longitude). Since there's no device
  sensor, they'll need to supply this — e.g. by pasting coordinates from
  their phone's maps app "share location" feature.
- **One or more azimuths** in degrees (0 = north, clockwise) they want
  plotted — e.g. the direction they plan to point an antenna.
- Optional, only if they care: a **distance** per azimuth (defaults to
  1000 m — mainly affects how much map is shown, not the antenna math), a
  **beamwidth** in degrees if they want a sector wedge instead of a single
  line (useful for a directional/sector antenna's coverage cone), and a
  short **label** per azimuth.
- Optional: if they know roughly when the underlying satellite image was
  taken, a capture date/time improves the shadow-based estimate — but it's
  fine to skip this; the tool defaults to the current time and says so in
  its output.

## 3. Run the mapper

From the `antenna-azimuth-mapper/` directory, run e.g.:

```bash
python -m azimuth_mapper.cli \
  --lat <LAT> --lon <LON> \
  --azimuth <AZ1> --distance <DIST1> --label "<LABEL1>" \
  [--azimuth <AZ2> --distance <DIST2> --label "<LABEL2>" ...] \
  --out /tmp/azimuth-map.html
```

If any azimuth needs a beamwidth (sector wedge instead of a plain line), or
if you're giving explicit labels for more than one azimuth, you must pass
`--beamwidth`/`--label` once per `--azimuth`, in the same order — use `""`
for the ones that don't need it (e.g. `--azimuth 45 --beamwidth "" --label
"Site A" --azimuth 120 --beamwidth 30 --label "Sector 2"`). `--distance` is
the only one of these that's fine to pass just once for "apply to all".

Add `--capture-datetime <ISO8601>` if the user gave you one.

Read the printed summary (destination coordinates per azimuth, and the
shadow/height estimate if one was found) before moving on, so you can
describe it accurately rather than just dumping the file.

## 4. Publish the result

Use the `Artifact` tool to publish the generated HTML file so the user sees
it inline. Then summarize in your own words: what's plotted, and — if a
shadow estimate came back — its confidence level and what it does and
doesn't tell them (height estimate near the origin, not a lean-direction
correction; see the README limitations section if they push on why).

## 5. Iterate

If the user wants to adjust an azimuth, add another one, or try a different
assumed capture time, just re-run step 3 with the new arguments and
re-publish — there's no need to repeat steps 1-2.
