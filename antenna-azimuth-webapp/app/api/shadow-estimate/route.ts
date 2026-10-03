import { NextRequest, NextResponse } from "next/server";

import { globalPixelToLonlat, metersPerPixel, type LatLon } from "@/lib/geometry";
import { bestEstimate, detectShadows } from "@/lib/shadow";
import { solarPosition } from "@/lib/solar";
import { deepestAvailableZoom, fetchSnapshot } from "@/lib/tiles";

// `sharp` needs native bindings, so this route must run on Node, not Edge.
export const runtime = "nodejs";

// No hardcoded preferred zoom — deepestAvailableZoom() defaults to the
// aerial mapset's own reported ceiling and probes downward from there;
// shadows need real resolution to be detectable at all.
const SNAPSHOT_SIZE_PX = 512;

interface RequestBody {
  lat: number;
  lon: number;
  captureDatetime?: string;
}

/**
 * Probe the imagery around a point for a shadow, and report the height of
 * whatever cast it.
 *
 * That height is the input the client needs to calibrate the imagery's
 * viewing geometry (see lib/relief.ts) — it is not an obstruction report.
 */
export async function POST(req: NextRequest) {
  let body: RequestBody;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { lat, lon, captureDatetime } = body;
  if (typeof lat !== "number" || typeof lon !== "number" || Number.isNaN(lat) || Number.isNaN(lon)) {
    return NextResponse.json({ error: "lat and lon must be numbers" }, { status: 400 });
  }
  if (lat < -85 || lat > 85 || lon < -180 || lon > 180) {
    return NextResponse.json({ error: "lat/lon out of range" }, { status: 400 });
  }

  const dt = captureDatetime ? new Date(captureDatetime) : new Date();
  if (Number.isNaN(dt.getTime())) {
    return NextResponse.json({ error: "captureDatetime is not a valid date" }, { status: 400 });
  }

  const origin: LatLon = { lat, lon };
  const sun = solarPosition(lat, lon, dt);
  const base = { sun, captureDatetime: dt.toISOString() };

  // Mapy.cz's aerial coverage is zoom-limited by country; fall back to the
  // deepest level that actually exists here rather than failing the whole request.
  let zoom: number;
  let snapshot;
  try {
    zoom = await deepestAvailableZoom(origin);
    snapshot = await fetchSnapshot(origin, zoom, SNAPSHOT_SIZE_PX);
  } catch (err) {
    return NextResponse.json(
      {
        ...base,
        found: false,
        error: `Could not fetch satellite imagery: ${err instanceof Error ? err.message : String(err)}`,
      },
      { status: 502 }
    );
  }

  const originPxInCrop: [number, number] = [snapshot.width / 2, snapshot.height / 2];
  const observations = detectShadows(snapshot.raw, snapshot.width, snapshot.height, originPxInCrop);
  const estimate = bestEstimate(observations, sun, metersPerPixel(lat, zoom));

  if (!estimate) {
    return NextResponse.json({ ...base, found: false, zoom });
  }

  const [globalOriginX, globalOriginY] = snapshot.originPx;
  const shadowLocation = globalPixelToLonlat(
    globalOriginX + estimate.centroidPx[0],
    globalOriginY + estimate.centroidPx[1],
    zoom
  );

  return NextResponse.json({
    ...base,
    found: true,
    zoom,
    shadowAzimuthDeg: estimate.shadowAzimuthDeg,
    angularErrorDeg: estimate.angularErrorDeg,
    shadowLengthM: estimate.shadowLengthM,
    referenceHeightM: estimate.referenceHeightM,
    confidence: estimate.confidence,
    shadowLocation,
  });
}
