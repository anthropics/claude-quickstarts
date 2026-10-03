# Antenna Azimuth Mapper — Web App

A real-time web app that plots compass azimuths (e.g. for aiming a
directional or sector antenna) from your **live browser GPS position** onto
a satellite map, and corrects those bearings for the angle the imagery was
shot from, so a target picked off a mast top or rooftop points where it
really is.

**Live demo:** https://antenna-azimuth-webapp.vercel.app

This is the browser-based companion to
[`../antenna-azimuth-mapper`](../antenna-azimuth-mapper), which is a
CLI/Cowork-skill version of the same idea for use inside a Claude session
(no device GPS there, so coordinates are typed in). This app exists
specifically for the piece the CLI/skill can't do: continuous, real GPS
tracking straight from your phone or laptop's browser.

## Setup

```bash
cd antenna-azimuth-webapp
cp .env.example .env.local   # fill in MAPY_CZ_API_KEY
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Satellite imagery
comes from the [Mapy.cz REST API](https://developer.mapy.com/rest-api-mapy-cz/)'s
aerial mapset, which requires an API key — register at api.mapy.cz to get
one, then set **`MAPY_CZ_API_KEY`** in `.env.local` for local dev and as a
*Production* environment variable on the Vercel project for the deployed
app. The key never reaches the browser: the on-screen map is served through
this app's own `/api/basemap/{z}/{x}/{y}` proxy, and the server-side tile
fetch used for shadow detection reads the key directly.

**GPS requires HTTPS** (or `localhost`) — `navigator.geolocation` is blocked
by browsers on a plain-HTTP, non-localhost origin. Local dev on `localhost`
works fine; once deployed (e.g. to Vercel) HTTPS is automatic.

## Usage

1. Allow the location permission prompt — your position appears as a white
   dot and the map recenters on it.
2. Add one or more azimuths (degrees, 0 = north) with a distance; give one
   a beamwidth to draw a sector wedge instead of a line, for planning a
   directional/sector antenna's coverage cone.
3. Calibrate the imagery once per site: mark an upright object's base and
   apparent top, then enter its height or press **From shadow** to measure
   it. Pick targets with **Pick target on map** and give each a height above
   ground to see its corrected bearing.
4. If GPS is unavailable or you want to check a different spot, type
   coordinates directly into the Latitude/Longitude fields — this switches
   to a manual override; "Use live GPS instead" switches back.

## What is and isn't distorted

The azimuth rays themselves are exact geodesic math from your GPS
coordinates. A satellite basemap and a vector basemap are both Web Mercator,
north-up, on the same tile grid, and a bearing here is computed from
latitude and longitude rather than from pixels — so **for two points on the
ground the azimuth is identical on either layer.** There is nothing to
correct there, and this app doesn't pretend otherwise.

What genuinely is displaced is anything standing *above* the ground.
Orthorectification places the terrain correctly using a bare-earth model,
but a mast, a rooftop or a chimney isn't in that model: its top is imaged
along the slanted line of sight to the satellite and lands away from its
true ground position by

    d = h · cot(E_sat)      along bearing   A_sat + 180°

where `h` is height above ground and `E_sat` / `A_sat` are the satellite's
elevation and azimuth. Picking an antenna link's far end by its mast top —
the normal way to pick it — therefore gives a bearing that's off. At 30 m
height and 30° off-nadir that's about 17 m of displacement: roughly **2° of
azimuth error at 500 m, 5° at 200 m**, and asymptotically nothing at long
range.

## How the correction works

`E_sat` and `A_sat` aren't published per tile, but they can be recovered
from the image, because a shadow and a lean are the same radial geometry
with the sun swapped for the satellite:

    shadow:  L_shadow = h · cot(E_sun),  bearing A_sun + 180°
    lean:    L_lean   = h · cot(E_sat),  bearing A_sat + 180°

The sun's position is computed astronomically, so measuring a reference
object's shadow gives its height `h`; with `h` known, that same object's
observed lean gives the satellite geometry. In the app: mark one upright
object's **base** and its **apparent top**, supply its height (or press
**From shadow** to measure it), and every elevated target you pick then gets
a corrected bearing alongside the raw one.

**Caveats worth keeping in mind.** The shadow measurement is a heuristic —
it detects an elongated dark blob and checks its direction against the true
sun, which is a sanity check rather than a guarantee it found the right
object; entering a known height by hand is more reliable. A calibration is
only valid for the patch of imagery it was measured on, since a basemap is a
mosaic of images from different passes. Ground-level targets need no
correction at all. And a separate real-world error source this app can't see
is basemap georeferencing offset — the aerial mosaic can sit several metres
off in places, which no amount of lean correction fixes.

## Layout

- `lib/geometry.ts`, `lib/solar.ts` — geodesic and solar-position math,
  ported 1:1 from the CLI's `azimuth_mapper/geometry.py` and `solar.py` so
  both tools agree.
- `lib/relief.ts` — the correction itself: recover the imagery's viewing
  geometry from one reference object, then map an apparent position back to
  its true ground position. Covered by `lib/relief.test.ts`.
- `lib/mapycz.ts` — resolves the Mapy.cz aerial mapset's tile URL template,
  attribution, and zoom range from its `tiles.json`, rather than hardcoding
  them (the docs say the attribution text can change). Covered by
  `lib/mapycz.test.ts`.
- `components/AzimuthMap.tsx` — a `react-leaflet` map with an aerial tile
  layer served through this app's own `/api/basemap/{z}/{x}/{y}` proxy (so
  the Mapy.cz API key never reaches the browser), your live GPS marker, the
  azimuth rays/wedges and the calibration/target markers (all computed
  client-side).
- `app/api/shadow-estimate/route.ts` (Node runtime — needs `sharp`) —
  server-side only, because reading pixel data from a cross-origin tile
  image in the browser would hit canvas CORS tainting: it fetches/stitches
  Mapy.cz aerial tiles, decodes them, and runs the shadow-detection +
  sun-position heuristic (`lib/shadow.ts`, `lib/tiles.ts` — ported from the
  CLI's `shadow_detect.py`/`correction.py`/`imagery.py`, since there's no OpenCV
  here). It only runs on demand, to avoid hammering the public tile endpoint.
- `app/api/export/route.ts` — renders the current view as a self-contained
  SVG for filing or sending on.
- `lib/persist.ts` — session state in `localStorage`, and the shareable link
  (encoded in the URL fragment, so a shared position never reaches a server
  log).

## Tests

```bash
npm test
```

Vitest covers the geometry, solar and relief modules — including a
round-trip that synthesises a lean for a known satellite geometry and checks
the calibration recovers it, and the hand-worked 2°-at-500 m case above.

## Deployment

Running live at https://antenna-azimuth-webapp.vercel.app. To deploy your
own copy:

```bash
npx vercel --cwd antenna-azimuth-webapp
```

or connect the repo in the Vercel dashboard with **Root Directory** set to
`antenna-azimuth-webapp`. No environment variables are required.

Note that Vercel enables **Vercel Authentication** on new projects, which
makes the deployment reachable only by members of the owning team — turn it
off under *Project Settings → Deployment Protection* if you want the URL to
be publicly usable (e.g. to open it on a phone that isn't logged into
Vercel).

### Continuous deployment

`.github/workflows/antenna-azimuth-webapp-deploy.yaml` ships this directory
to production on every push to `main` that touches it, and can also be run
by hand from the repository's **Actions** tab (*Run workflow*) — which is
how to redeploy when nothing under `antenna-azimuth-webapp/` has changed.
Lint and the Vitest suite run first, so a failing test blocks the deploy.

It needs one repository secret, **`VERCEL_TOKEN`** — create it under
*Vercel → Account Settings → Tokens*, scoped to the team that owns the
project, then add it under *GitHub → Settings → Secrets and variables →
Actions*. The project and team IDs are in the workflow's `env:` block; a
guard on `github.repository` stops forks from deploying into them, so
change both values (and the guard) if you run your own copy.

Because this targets an existing Vercel project through the CLI rather than
linking the repository in the dashboard, it leaves the project's Deployment
Protection setting alone — a URL that is already public stays public.
