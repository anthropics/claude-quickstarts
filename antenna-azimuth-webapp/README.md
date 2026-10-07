# Antenna Azimuth Mapper — Web App

A real-time web app that plots compass azimuths (e.g. for aiming a
directional or sector antenna) from your **live browser GPS position** onto
a satellite map, and corrects those bearings for the angle the imagery was
shot from, so a target picked off a mast top or rooftop points where it
really is.

**Existing public deployment:** https://antenna-azimuth-webapp-sigma.vercel.app

The project/PDF/completion changes described below are currently in the local
working copy. This public deployment has not been updated with them.

## Phone use

The app is designed as a responsive web page for iPhone and Android; real
device sensor verification remains necessary. GPS and typed
map bearings do not require a compass sensor. Enable the separate phone
compass with its button; Safari may request permission, while other
browsers may expose absolute orientation events without a separate prompt.
Hold the phone flat in portrait orientation. Relative rotation events,
uncalibrated readings and stale readings are not shown as compass headings.
The sensor's north reference may differ from the map's true north: it is an
orientation aid, not verification of the installed antenna's alignment.
The GPS course readout measures movement, not the direction the phone faces.

Aerial imagery remains the primary map. Without a Mapy.com key the app uses
the public **ČÚZK Ortofoto** service for the Czech Republic. Its Web Mercator
cache, attribution and native zoom limits are taken from the official service
metadata (currently levels 6–20, not every level listed in tileInfo.lods).
With a configured `MAPY_CZ_API_KEY`, the app uses Mapy.com's aerial mapset.
If the selected provider's metadata or tiles fail,
the app shows an explicitly labelled OpenStreetMap street-map fallback and
disables imagery calibration. Retry aerial imagery from the status panel below
the map; status messages do not cover the imagery or map controls.
The maximum zoom follows the provider's metadata; enlarging beyond the
native imagery resolution does not add detail. The street-map fallback
uses normal browser requests and caching, visible attribution, and no
tile prefetch or offline download. See the [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/).

No radio-signal measurement or radio-device integration is included.

This is the browser-based companion to
[`../antenna-azimuth-mapper`](../antenna-azimuth-mapper), which is a
CLI/Cowork-skill version of the same idea for use inside a Claude session
(no device GPS there, so coordinates are typed in). This app exists
specifically for the piece the CLI/skill can't do: continuous, real GPS
tracking straight from your phone or laptop's browser.

## Setup

Use **Node.js 24.14.0 or later** for this working copy. The pinned PDF.js
worker is copied from the installed dependency to `public/pdf.worker.min.mjs`
by the `predev` and `prebuild` scripts. Run the npm scripts so that the
worker matches the installed parser version.

This App Router project aligns React/React DOM and their TypeScript types
with React 19, and uses React Leaflet 5. Next.js 15's App Router uses React
19 even when an older React package is installed. React Leaflet 4's map
ref callback can initialize the same DOM container twice during React 19
development ref replay; v5 guards initialization with a map-instance ref.
Strict Mode remains enabled. See the [Next.js 15 React guidance](https://nextjs.org/blog/next-15#react-19),
the [React Leaflet 5 release](https://github.com/PaulLeCam/react-leaflet/releases/tag/v5.0.0),
and its [MapContainer implementation](https://github.com/PaulLeCam/react-leaflet/blob/v5.0.0/packages/react-leaflet/src/MapContainer.tsx).

```bash
cd antenna-azimuth-webapp
# Copy .env.example to .env.local for Supabase project sync.
# MAPY_CZ_API_KEY is optional for Czech aerial imagery.
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Czech aerial imagery works
without environment variables through the official [ČÚZK service](https://ags.cuzk.gov.cz/arcgis1/rest/services/ORTOFOTO_WM/MapServer).
Coverage is the Czech Republic; it is not a global imagery service.
To select Mapy.com, set **`MAPY_CZ_API_KEY`** in `.env.local` or your hosting
environment. The key stays on the server behind `/api/basemap/{z}/{x}/{y}`.
Neither provider's imagery has a verified exact capture timestamp in this app:
shadow-based height estimation requires that timestamp and rejects requests
without it. Enter a known object height manually for calibration.

**GPS requires HTTPS** (or `localhost`) — `navigator.geolocation` is blocked
by browsers on a plain-HTTP, non-localhost origin. Local dev on `localhost`
works fine; once deployed (e.g. to Vercel) HTTPS is automatic.

## Projekty, PDF a dokončení montáže

1. Otevřete **Projekty a nahrání PDF** a přihlaste se. Nový účet vytvořte
   v téže obrazovce; pokud Supabase vyžaduje potvrzení e-mailu, nejprve
   dokončete potvrzení a poté se přihlaste.
2. Založte projekt a nahrajte PDF s tabulkou sektorů, nebo přidejte sektory
   ručně. Import probíhá v prohlížeči. Před uložením zkontrolujte název
   lokality, azimuty, souřadnice a každý náklon podle originálního zadání.
3. **Mechanický a elektrický náklon mají samostatná pole.** Prázdná hodnota
   znamená, že údaj chybí; není zaměněna za 0°. U nejednoznačné tabulky
   zůstane varování a text s číslem zdrojové stránky. Obecné pole „Tilt“
   se samo nepřiřadí k mechanickému nebo elektrickému náklonu.
4. Zaškrtněte potvrzení kontroly a zvolte **Potvrdit, uložit a načíst do
   mapy**. Směry se převezmou ze sektorů projektu; náklony jsou zobrazeny
   jako požadované hodnoty ze zadání. Pokud zadání nemá souřadnice,
   určete polohu ručně nebo výslovně použijte GPS.
5. Po skutečném nasměrování každého sektoru stiskněte **Potvrdit
   nasměrování**. Uloží se čas potvrzení. Jakmile jsou potvrzené všechny
   sektory, projekt se přesune do **Hotové**.
6. Tlačítkem **Vrátit mezi rozpracované** lze potvrzení sektoru zrušit;
   projekt se znovu objeví mezi rozpracovanými. Změna údajů sektoru
   v editoru jeho potvrzení ruší. Změna souřadnic projektu znovu otevře
   všechny jeho sektory.

Potvrzení zaznamenává úkon montéra. Aplikace neměří skutečné nastavení
antény ani splnění požadovaného náklonu. Kompas telefonu je orientační
pomůcka; GPS kurz a směr natočení telefonu jsou odlišné údaje.

### Podporované podklady a limity

Importer zpracovává textová PDF s tabulkami sektorů, nejvýše 20 MiB,
50 stran a 300 sektorů. Podporuje desetinnou čárku a zachovává rozdíl
mezi chybějícím údajem a nulou. Naskenované PDF bez textové vrstvy
vyžaduje ruční přepis; OCR není součástí této verze. Nejednoznačný,
obrácený či odlišně uspořádaný dokument nemusí být rozpoznán správně.
Kontrola před uložením je povinná. Parser byl ověřen syntetickými testy;
skutečné uživatelské zadání zatím nebylo poskytnuto.

### Synchronizace a přístup

Na telefonu i počítači použijte stejný účet a stejnou nasazenou verzi
aplikace. Seznam projektů se načítá při otevření, návratu do okna a
ručním obnovení. Ukládání vyžaduje internet; tato verze nemá frontu
změn pro práci bez připojení. Zápis používá číslo revize: souběžná
úprava staršího stavu vyvolá upozornění k obnovení projektu.

Projekty a historie revizí jsou oddělené podle vlastníka pomocí
Supabase RLS. Originální PDF jsou v privátním bucketu
`azimuth-assignments`; otevření dokumentu používá krátkodobý podepsaný
odkaz. Starší dokumenty zůstávají zachovány, pokud na ně odkazuje
historie projektu.

Pro vlastní prostředí nastavte podle `.env.example`:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
```

Do klienta patří pouze publishable key. Serverové a servisní klíče se
do proměnných `NEXT_PUBLIC_*` nevkládají. Schéma této pracovní kopie
je v [azimuth-supabase-schema.sql](supabase/schema.sql);
při nasazení do jiného prostředí je nutné je aplikovat a nastavit
povolenou adresu aplikace v Supabase Auth. Vybraný existující projekt
Supabase už má schéma aplikované.

## Usage

1. Allow the location permission prompt — your position appears as a white
   dot and the map recenters on it.
2. Add one or more azimuths (degrees, 0 = north) with a distance; give one
   a beamwidth to draw a sector wedge instead of a line, for planning a
   directional/sector antenna's coverage cone.
3. Calibrate the imagery once per site: mark an upright object's base and
   apparent top, then enter its known height. Automatic shadow estimation is
   unavailable without a verified capture timestamp. Pick targets with **Pick target on map** and give each a height above
   ground to see its corrected bearing.
4. If GPS is unavailable or you want to check a different spot, type
   coordinates into the position fields and press **Použít souřadnice**.
   Empty fields do not move the map to zero coordinates. Use the GPS button
   to return to the device position.

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
object's **base** and its **apparent top**, supply its known height, and
every elevated target you pick then gets
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
- `lib/mapycz.ts` — resolves the selected ČÚZK or Mapy.com provider, its
  tile URL template, attribution and available native zoom range from
  provider metadata. Covered by `lib/mapycz.test.ts`.
- `lib/pdf-import.ts`, `lib/read-pdf.ts` — bounded text-PDF parsing and
  browser extraction; ambiguous values remain available for user review.
- `lib/projects.ts`, `lib/project-store.ts`, `lib/supabase-client.ts` —
  project validation, explicit sector completion, authenticated persistence
  and revision checks.
- `components/ProjectWorkspace.tsx` — login, project library, reviewed PDF
  import, editing, and the Rozpracované / Hotové views.
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

As of 7 October 2026, **76 tests pass** and the final production build passes.
The live database checks passed in rollback transactions; eight related checks
were repeated after changing the revision conflict to HTTP409. Browser tests
verified a synthetic PDF import, private storage, synchronization between two
isolated authenticated clients, completion, undo and a stale-revision conflict.
Real ČÚZK metadata and aerial tiles passed a fresh browser check.
These checks do not establish physical phone sensor accuracy, screen-reader
behavior, registration email delivery, or extraction of an unseen customer PDF.
Temporary QA account/data/credentials were removed. The public Vercel version
has not been updated. Ensure deployment CI uses Node24.14.0 or newer.

Vitest covers PDF table parsing, project validation/completion, map-provider
metadata, and the geometry, solar and relief modules — including a
round-trip that synthesises a lean for a known satellite geometry and checks
the calibration recovers it, and the hand-worked 2°-at-500 m case above.

## Deployment

The deployment address is https://antenna-azimuth-webapp-sigma.vercel.app. To deploy your
own copy:

```bash
npx vercel --cwd antenna-azimuth-webapp
```

or connect the repo in the Vercel dashboard with **Root Directory** set to
`antenna-azimuth-webapp`. No key is needed for ČÚZK orthoimagery in Czechia.
Optionally set `MAPY_CZ_API_KEY` to use Mapy.com instead. If the selected
upstream service is unavailable, the map falls back to the street layer and
imagery calibration is disabled.

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
TypeScript checks and the Vitest suite run first, so a failing check blocks the deploy.

It needs one repository secret, **`VERCEL_TOKEN`** — create it under
*Vercel → Account Settings → Tokens*, scoped to the team that owns the
project, then add it under *GitHub → Settings → Secrets and variables →
Actions*. The project and team IDs are in the workflow's `env:` block; a
guard on `github.repository` stops forks from deploying into them, so
change both values (and the guard) if you run your own copy.

Because this targets an existing Vercel project through the CLI rather than
linking the repository in the dashboard, it leaves the project's Deployment
Protection setting alone — a URL that is already public stays public.

