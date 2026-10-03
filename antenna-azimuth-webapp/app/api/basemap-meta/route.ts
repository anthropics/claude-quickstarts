import { NextResponse } from "next/server";

import { getAerialTileset } from "@/lib/mapycz";

/**
 * Exposes just the attribution text and max zoom from the Mapy.cz aerial
 * tileset — never the tile URL template itself, which embeds the API key.
 *
 * Exists so the legally-relevant attribution string shown on the map comes
 * from Mapy.cz's own tiles.json (which the docs say can change) rather than
 * hand-copied text that could drift out of compliance.
 */
export async function GET() {
  try {
    const { attribution, maxZoom } = await getAerialTileset();
    return NextResponse.json({ attribution, maxZoom });
  } catch {
    return NextResponse.json({ error: "Basemap tileset unavailable" }, { status: 502 });
  }
}
