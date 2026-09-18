import { NextRequest } from "next/server";

import { getAerialTileset, resolveTileUrl } from "@/lib/mapycz";

/**
 * Passthrough proxy for the on-screen Mapy.cz aerial tile layer.
 *
 * The client-facing `<TileLayer>` must never see the real Mapy.cz URL —
 * it embeds the API key — so this route resolves it server-side and
 * streams the tile bytes back. No `sharp` involved (pure passthrough), so
 * this runs on the Edge runtime for lower tile latency, unlike the
 * Node-only sharp-based routes elsewhere in this app.
 */
export const runtime = "edge";

const MAX_ZOOM_CAP = 22; // generous upper bound; the real ceiling comes from the tileset itself

function parseTileCoord(raw: string): number | null {
  if (!/^-?\d+$/.test(raw)) return null;
  return Number(raw);
}

export async function GET(_req: NextRequest, context: { params: Promise<{ z: string; x: string; y: string }> }) {
  const { z: zRaw, x: xRaw, y: yRaw } = await context.params;
  const z = parseTileCoord(zRaw);
  const x = parseTileCoord(xRaw);
  const y = parseTileCoord(yRaw);

  if (z === null || x === null || y === null || z < 0 || z > MAX_ZOOM_CAP) {
    return new Response("Invalid tile coordinates", { status: 400 });
  }

  const nTiles = 2 ** z;
  if (y < 0 || y >= nTiles) {
    return new Response("Tile y out of range", { status: 400 });
  }
  // Longitude wraps around the world; x is wrapped rather than rejected, the
  // same logic fetchSnapshot() already uses for the server-side mosaic path.
  const wrappedX = ((x % nTiles) + nTiles) % nTiles;

  let upstreamUrl: string;
  try {
    const tileset = await getAerialTileset();
    upstreamUrl = resolveTileUrl(tileset.tileUrlTemplate, z, wrappedX, y);
  } catch {
    return new Response("Basemap tileset unavailable", { status: 502 });
  }

  const upstream = await fetch(upstreamUrl);
  if (!upstream.ok || !upstream.body) {
    return new Response("Tile fetch failed", { status: upstream.status === 404 ? 404 : 502 });
  }

  return new Response(upstream.body, {
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "image/png",
      // Satellite tiles are effectively immutable; cache aggressively to keep
      // both our function invocations and Mapy.cz's own load down.
      "cache-control": "public, max-age=604800, immutable",
    },
  });
}
