import { NextRequest, NextResponse } from "next/server";
import sharp from "sharp";

import {
  chooseZoomForSpan,
  destinationPoint,
  lonlatToGlobalPixel,
  metersPerPixel,
  type LatLon,
} from "@/lib/geometry";
import { deepestAvailableZoom, fetchSnapshot } from "@/lib/tiles";

// `sharp` needs native bindings, so this route must run on Node, not Edge.
export const runtime = "nodejs";

const SIZE_PX = 800;
const RAY_COLORS = ["#ff6a3d", "#3ea1ff", "#ffd23f", "#3ddc84", "#c792ff"];

interface ExportRay {
  label?: string;
  azimuthDeg: number;
  distanceM: number;
  beamwidthDeg?: number | null;
}

interface ExportBody {
  origin: LatLon;
  rays: ExportRay[];
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function niceScaleLength(rawM: number): number {
  if (rawM <= 0) return 10;
  const magnitude = 10 ** Math.floor(Math.log10(rawM));
  for (const mult of [1, 2, 5, 10]) {
    if (magnitude * mult >= rawM) return magnitude * mult;
  }
  return magnitude * 10;
}

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

/**
 * Render the current view as a self-contained SVG — imagery embedded as a
 * data URI, rays drawn as vectors — mirroring what the Python CLI's
 * `render.py` produces, so a session can be filed or sent on.
 */
export async function POST(req: NextRequest) {
  let body: ExportBody;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { origin, rays } = body;
  if (!origin || typeof origin.lat !== "number" || typeof origin.lon !== "number") {
    return NextResponse.json({ error: "origin {lat, lon} is required" }, { status: 400 });
  }
  if (!Array.isArray(rays) || rays.length === 0) {
    return NextResponse.json({ error: "at least one ray is required" }, { status: 400 });
  }

  const maxDistance = Math.max(...rays.map((r) => r.distanceM || 0), 100);
  const wanted = chooseZoomForSpan(maxDistance, origin.lat, SIZE_PX);

  let zoom: number;
  let snapshot;
  try {
    zoom = await deepestAvailableZoom(origin, wanted, Math.min(wanted, 10));
    snapshot = await fetchSnapshot(origin, zoom, SIZE_PX);
  } catch (err) {
    return NextResponse.json(
      { error: `Could not fetch satellite imagery: ${err instanceof Error ? err.message : String(err)}` },
      { status: 502 }
    );
  }

  const png = await sharp(snapshot.raw, {
    raw: { width: snapshot.width, height: snapshot.height, channels: 3 },
  })
    .png()
    .toBuffer();
  const dataUri = `data:image/png;base64,${png.toString("base64")}`;

  const [originGx, originGy] = lonlatToGlobalPixel(origin, zoom);
  const [cropX, cropY] = snapshot.originPx;
  const ox = originGx - cropX;
  const oy = originGy - cropY;

  const toLocal = (p: LatLon): [number, number] => {
    const [gx, gy] = lonlatToGlobalPixel(p, zoom);
    return [gx - cropX, gy - cropY];
  };

  const parts: string[] = [];
  rays.forEach((ray, i) => {
    const color = RAY_COLORS[i % RAY_COLORS.length];
    if (ray.beamwidthDeg) {
      const start = ray.azimuthDeg - ray.beamwidthDeg / 2;
      const end = ray.azimuthDeg + ray.beamwidthDeg / 2;
      const steps = Math.max(2, Math.round(Math.abs(ray.beamwidthDeg) / 3));
      const pts: string[] = [`${ox.toFixed(1)},${oy.toFixed(1)}`];
      for (let s = 0; s <= steps; s++) {
        const [x, y] = toLocal(
          destinationPoint(origin, start + ((end - start) * s) / steps, ray.distanceM)
        );
        pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      }
      parts.push(
        `<polygon points="${pts.join(" ")}" fill="${color}" fill-opacity="0.22" stroke="${color}" stroke-width="2"/>`
      );
    } else {
      const [x, y] = toLocal(destinationPoint(origin, ray.azimuthDeg, ray.distanceM));
      parts.push(
        `<line x1="${ox.toFixed(1)}" y1="${oy.toFixed(1)}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${color}" stroke-width="3" stroke-linecap="round"/>`,
        `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" fill="${color}"/>`
      );
    }

    const [lx, ly] = toLocal(destinationPoint(origin, ray.azimuthDeg, ray.distanceM * 0.55));
    const label = escapeXml(ray.label || `${ray.azimuthDeg.toFixed(1)}°`);
    parts.push(
      `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" fill="${color}" font-size="13" font-family="monospace" font-weight="600" paint-order="stroke" stroke="#0009" stroke-width="3">${label}</text>`
    );
  });

  const mpp = metersPerPixel(origin.lat, zoom);
  const barM = niceScaleLength(SIZE_PX * 0.25 * mpp);
  const barPx = barM / mpp;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE_PX}" height="${SIZE_PX}" viewBox="0 0 ${SIZE_PX} ${SIZE_PX}">
<image href="${dataUri}" x="0" y="0" width="${SIZE_PX}" height="${SIZE_PX}"/>
${parts.join("\n")}
<circle cx="${ox.toFixed(1)}" cy="${oy.toFixed(1)}" r="6" fill="#fff" stroke="#111" stroke-width="2"/>
<circle cx="${SIZE_PX - 46}" cy="46" r="26" fill="#0007" stroke="#fff" stroke-width="1.5"/>
<line x1="${SIZE_PX - 46}" y1="68" x2="${SIZE_PX - 46}" y2="24" stroke="#fff" stroke-width="2"/>
<text x="${SIZE_PX - 46}" y="22" fill="#fff" font-size="13" font-family="sans-serif" font-weight="700" text-anchor="middle">N</text>
<line x1="16" y1="${SIZE_PX - 22}" x2="${(16 + barPx).toFixed(1)}" y2="${SIZE_PX - 22}" stroke="#fff" stroke-width="3"/>
<text x="16" y="${SIZE_PX - 30}" fill="#fff" font-size="12" font-family="monospace" paint-order="stroke" stroke="#0009" stroke-width="3">${formatDistance(barM)}</text>
<text x="16" y="20" fill="#fff" font-size="11" font-family="monospace" paint-order="stroke" stroke="#0009" stroke-width="3">${origin.lat.toFixed(6)}, ${origin.lon.toFixed(6)} · z${zoom}</text>
</svg>`;

  return new NextResponse(svg, {
    headers: {
      "content-type": "image/svg+xml; charset=utf-8",
      "content-disposition": 'attachment; filename="azimuth-map.svg"',
    },
  });
}
