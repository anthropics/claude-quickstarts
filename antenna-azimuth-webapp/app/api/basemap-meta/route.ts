import { NextResponse } from "next/server";

import { getAerialTileset } from "@/lib/mapycz";

/**
 * Exposes just the attribution text and zoom range from the Mapy.cz aerial
 * tileset — never the tile URL template itself, which embeds the API key.
 *
 * Exists so the legally-relevant attribution string shown on the map comes
 * from Mapy.cz's own tiles.json (which the docs say can change) rather than
 * hand-copied text that could drift out of compliance.
 */
export const runtime = "edge";

export async function GET() {
  try {
    const { name, attribution, minZoom, maxZoom } = await getAerialTileset();
    return NextResponse.json({ name, attribution, minZoom, maxZoom });
  } catch (error) {
    const errorType = error instanceof Error ? error.name : "UnknownError";
    const cause = error instanceof Error ? error.cause : null;
    const code = cause && typeof cause === "object" && "code" in cause ? String(cause.code) : "";
    console.warn("[basemap-meta] resolver failed", { errorType, code: /^[A-Z0-9_]+$/.test(code) ? code : undefined });
    return NextResponse.json({ error: "Basemap tileset unavailable" }, { status: 502 });
  }
}
