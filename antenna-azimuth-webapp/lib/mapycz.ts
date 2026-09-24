/**
 * Mapy.cz aerial-imagery tileset resolver — server-only.
 *
 * Rather than hardcoding a guessed tile URL, this fetches the mapset's
 * `tiles.json` once and treats it as the source of truth for the upstream
 * tile URL template, the valid zoom range, and the attribution text. That
 * is what Mapy.cz's own docs describe `tiles.json` as being for: the
 * standard TileJSON response includes `tiles[]` (URL templates), `minzoom`/
 * `maxzoom`, and the currently-valid `attribution` string, which the docs
 * say can change over time — reading it live is more correct than copying
 * text by hand once and letting it drift out of compliance.
 *
 * Field names below follow the open TileJSON spec, not anything Mapy.cz-
 * specific, but the exact response shape has not been directly verified
 * (api.mapy.cz is unreachable from this environment). Parsing is
 * deliberately defensive — missing fields fall back to sane defaults —
 * so a slightly different real response degrades gracefully instead of
 * throwing, and the fix for a wrong assumption stays localized to this
 * file.
 */

const AERIAL_TILES_JSON_URL = (apiKey: string) =>
  `https://api.mapy.cz/v1/maptiles/aerial/tiles.json?apikey=${encodeURIComponent(apiKey)}`;

const FALLBACK_MIN_ZOOM = 0;
const FALLBACK_MAX_ZOOM = 19;
const FALLBACK_ATTRIBUTION = "Map data © Seznam.cz, a.s. and its licensors";

export interface AerialTileset {
  /** URL template containing {z}/{x}/{y} (and the API key), resolved from tiles.json. Server-side use only. */
  tileUrlTemplate: string;
  minZoom: number;
  maxZoom: number;
  attribution: string;
}

interface TileJsonResponse {
  tiles?: unknown;
  minzoom?: unknown;
  maxzoom?: unknown;
  attribution?: unknown;
}

function parseTileJson(json: TileJsonResponse): AerialTileset {
  const template = Array.isArray(json.tiles) && typeof json.tiles[0] === "string" ? json.tiles[0] : null;
  if (!template) {
    throw new Error("Mapy.cz tiles.json response has no usable tiles[] URL template");
  }
  return {
    tileUrlTemplate: template,
    minZoom: typeof json.minzoom === "number" ? json.minzoom : FALLBACK_MIN_ZOOM,
    maxZoom: typeof json.maxzoom === "number" ? json.maxzoom : FALLBACK_MAX_ZOOM,
    attribution: typeof json.attribution === "string" && json.attribution ? json.attribution : FALLBACK_ATTRIBUTION,
  };
}

let cached: Promise<AerialTileset> | null = null;

/** Fetches and caches the aerial mapset's TileJSON for the lifetime of this server instance. */
export async function getAerialTileset(): Promise<AerialTileset> {
  if (cached) return cached;

  const apiKey = process.env.MAPY_CZ_API_KEY;
  if (!apiKey) {
    throw new Error("MAPY_CZ_API_KEY is not set");
  }

  cached = (async () => {
    const resp = await fetch(AERIAL_TILES_JSON_URL(apiKey));
    if (!resp.ok) {
      throw new Error(`Mapy.cz tiles.json fetch failed (${resp.status})`);
    }
    return parseTileJson((await resp.json()) as TileJsonResponse);
  })().catch((err) => {
    // Don't cache a failure — the next call should retry rather than being
    // stuck rejecting for the life of the server instance.
    cached = null;
    throw err;
  });

  return cached;
}

/** Substitutes {z}/{x}/{y} into a resolved tile URL template. */
export function resolveTileUrl(template: string, z: number, x: number, y: number): string {
  return template.replace("{z}", String(z)).replace("{x}", String(x)).replace("{y}", String(y));
}
