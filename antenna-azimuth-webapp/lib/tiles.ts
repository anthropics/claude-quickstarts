/**
 * Fetch and stitch Mapy.cz aerial-imagery tiles around a point — server-only
 * (uses `sharp` and Node's `fetch`). Ported from
 * antenna-azimuth-mapper/azimuth_mapper/imagery.py, which still targets Esri
 * World Imagery — the two projects intentionally use different providers.
 *
 * Mapy.cz's aerial mapset is itself a mosaic assembled from source images of
 * different dates and viewing angles, which is exactly why the shadow-based
 * estimate in shadow.ts has to stay a heuristic: there is no single, known
 * capture geometry for a tile.
 */
import sharp from "sharp";

import { type LatLon, TILE_SIZE_PX, lonlatToGlobalPixel } from "./geometry";
import { getAerialTileset, resolveTileUrl } from "./mapycz";

async function tileUrl(z: number, y: number, x: number): Promise<string> {
  const tileset = await getAerialTileset();
  return resolveTileUrl(tileset.tileUrlTemplate, z, x, y);
}

/**
 * Small bounded tile cache.
 *
 * Calibrating and then probing a few targets hits the same handful of tiles
 * repeatedly, and this is a public endpoint we don't want to hammer. Entries
 * are raw PNG bytes; the map is capped and evicted oldest-first (insertion
 * order, re-inserting on hit to make it LRU rather than FIFO).
 */
const TILE_CACHE_MAX = 64;
const tileCache = new Map<string, Buffer>();

async function fetchTile(z: number, y: number, x: number): Promise<Buffer> {
  const key = `${z}/${y}/${x}`;
  const hit = tileCache.get(key);
  if (hit) {
    tileCache.delete(key);
    tileCache.set(key, hit);
    return hit;
  }

  const url = await tileUrl(z, y, x);
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Tile fetch failed (${resp.status}) for z${z}/${x}/${y}`);
  }
  const buf = Buffer.from(await resp.arrayBuffer());

  tileCache.set(key, buf);
  if (tileCache.size > TILE_CACHE_MAX) {
    const oldest = tileCache.keys().next().value;
    if (oldest !== undefined) tileCache.delete(oldest);
  }
  return buf;
}

/**
 * Deepest zoom Mapy.cz actually serves at this location, at or below
 * `preferred` (defaulting to the aerial mapset's own documented ceiling).
 *
 * Mapy.cz's aerial coverage is zoom-limited by country — the whole world
 * only to z13, Czech Republic to z20, several neighbors to z19 — so asking
 * for a level that isn't there returns an error tile; probe downward
 * instead of failing the request outright.
 */
export async function deepestAvailableZoom(
  center: LatLon,
  preferred?: number,
  floor = 12
): Promise<number> {
  const tileset = await getAerialTileset();
  const start = Math.min(preferred ?? tileset.maxZoom, tileset.maxZoom);
  for (let zoom = start; zoom >= floor; zoom--) {
    const [x, y] = lonlatToGlobalPixel(center, zoom);
    const tx = Math.floor(x / TILE_SIZE_PX);
    const ty = Math.floor(y / TILE_SIZE_PX);
    try {
      await fetchTile(zoom, ty, tx);
      return zoom;
    } catch {
      // Try the next level down.
    }
  }
  throw new Error(`No Mapy.cz aerial imagery available at zoom ${floor}-${start} for this location`);
}

export interface MapSnapshot {
  /** Raw RGB pixel buffer, width * height * 3 bytes, row-major. */
  raw: Buffer;
  width: number;
  height: number;
  center: LatLon;
  zoom: number;
  /** Global Web Mercator pixel coords of the image's top-left corner. */
  originPx: [number, number];
}

/** Fetch just enough Mapy.cz aerial tiles to cover a sizePx square centered on center. */
export async function fetchSnapshot(
  center: LatLon,
  zoom: number,
  sizePx = 512
): Promise<MapSnapshot> {
  const [centerX, centerY] = lonlatToGlobalPixel(center, zoom);
  const half = sizePx / 2;
  const left = centerX - half;
  const top = centerY - half;
  const right = centerX + half;
  const bottom = centerY + half;

  const firstTileX = Math.floor(left / TILE_SIZE_PX);
  const firstTileY = Math.floor(top / TILE_SIZE_PX);
  const lastTileX = Math.floor((right - 1) / TILE_SIZE_PX);
  const lastTileY = Math.floor((bottom - 1) / TILE_SIZE_PX);
  const nTiles = 2 ** zoom;

  const mosaicW = (lastTileX - firstTileX + 1) * TILE_SIZE_PX;
  const mosaicH = (lastTileY - firstTileY + 1) * TILE_SIZE_PX;

  const tileCoords: { tx: number; ty: number }[] = [];
  for (let ty = firstTileY; ty <= lastTileY; ty++) {
    for (let tx = firstTileX; tx <= lastTileX; tx++) {
      tileCoords.push({ tx, ty });
    }
  }

  const composites = await Promise.all(
    tileCoords.map(async ({ tx, ty }) => {
      const wrappedX = ((tx % nTiles) + nTiles) % nTiles;
      const buf = await fetchTile(zoom, ty, wrappedX);
      return {
        input: buf,
        left: (tx - firstTileX) * TILE_SIZE_PX,
        top: (ty - firstTileY) * TILE_SIZE_PX,
      };
    })
  );

  const mosaicOriginX = firstTileX * TILE_SIZE_PX;
  const mosaicOriginY = firstTileY * TILE_SIZE_PX;
  const cropLeft = Math.round(left - mosaicOriginX);
  const cropTop = Math.round(top - mosaicOriginY);

  const { data, info } = await sharp({
    create: {
      width: mosaicW,
      height: mosaicH,
      channels: 3,
      background: { r: 0, g: 0, b: 0 },
    },
  })
    .composite(composites)
    .extract({ left: cropLeft, top: cropTop, width: sizePx, height: sizePx })
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  return {
    raw: data,
    width: info.width,
    height: info.height,
    center,
    zoom,
    originPx: [mosaicOriginX + cropLeft, mosaicOriginY + cropTop],
  };
}
