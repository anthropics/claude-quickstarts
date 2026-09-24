/**
 * Geodesic and Web Mercator math, ported 1:1 from
 * antenna-azimuth-mapper/azimuth_mapper/geometry.py so the web app and the
 * CLI/skill agree on the same math.
 */

export const WGS84_RADIUS_M = 6371008.8; // mean earth radius, good enough for tens-of-km spans
export const TILE_SIZE_PX = 256;

export interface LatLon {
  lat: number;
  lon: number;
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

function toDeg(rad: number): number {
  return (rad * 180) / Math.PI;
}

/** Forward geodesic: point reached from origin along azimuthDeg for distanceM. */
export function destinationPoint(origin: LatLon, azimuthDeg: number, distanceM: number): LatLon {
  const lat1 = toRad(origin.lat);
  const lon1 = toRad(origin.lon);
  const brng = toRad(((azimuthDeg % 360) + 360) % 360);
  const delta = distanceM / WGS84_RADIUS_M;

  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(delta) + Math.cos(lat1) * Math.sin(delta) * Math.cos(brng)
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(brng) * Math.sin(delta) * Math.cos(lat1),
      Math.cos(delta) - Math.sin(lat1) * Math.sin(lat2)
    );

  return { lat: toDeg(lat2), lon: (((toDeg(lon2) + 540) % 360) + 360) % 360 - 180 };
}

/** Initial compass bearing in degrees from point a to point b. */
export function bearingBetween(a: LatLon, b: LatLon): number {
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const dlon = toRad(b.lon - a.lon);
  const x = Math.sin(dlon) * Math.cos(lat2);
  const y = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dlon);
  return (((toDeg(Math.atan2(x, y)) % 360) + 360) % 360);
}

export function haversineDistanceM(a: LatLon, b: LatLon): number {
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const dlat = lat2 - lat1;
  const dlon = toRad(b.lon - a.lon);
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon / 2) ** 2;
  return 2 * WGS84_RADIUS_M * Math.asin(Math.sqrt(h));
}

/** Ground resolution of a Web Mercator tile at the given latitude/zoom. */
export function metersPerPixel(lat: number, zoom: number): number {
  return (Math.cos(toRad(lat)) * 2 * Math.PI * WGS84_RADIUS_M) / (TILE_SIZE_PX * 2 ** zoom);
}

/** Web Mercator pixel coordinates at the given zoom, in the global tile pixel space. */
export function lonlatToGlobalPixel(point: LatLon, zoom: number): [number, number] {
  const latRad = toRad(point.lat);
  const n = 2 ** zoom;
  const x = ((point.lon + 180.0) / 360.0) * n * TILE_SIZE_PX;
  const y =
    ((1.0 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2.0) * n * TILE_SIZE_PX;
  return [x, y];
}

export function globalPixelToLonlat(x: number, y: number, zoom: number): LatLon {
  const n = 2 ** zoom;
  const lon = (x / (n * TILE_SIZE_PX)) * 360.0 - 180.0;
  const yNorm = 1.0 - (2.0 * y) / (n * TILE_SIZE_PX);
  const latRad = Math.atan(Math.sinh(Math.PI * yNorm));
  return { lat: toDeg(latRad), lon };
}

/** Pick the smallest zoom whose ground span at least covers 2x the max distance. */
export function chooseZoomForSpan(distanceM: number, lat: number, targetPx = 640): number {
  // 20 is Mapy.cz's documented aerial-imagery ceiling (Czech Republic);
  // deepestAvailableZoom() clamps to whatever the tileset actually reports
  // and probes downward from there for locations with shallower coverage.
  for (let zoom = 20; zoom >= 1; zoom--) {
    const spanM = metersPerPixel(lat, zoom) * targetPx;
    if (spanM >= 2 * distanceM) return zoom;
  }
  return 1;
}
