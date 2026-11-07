import { describe, expect, it } from "vitest";

import {
  bearingBetween,
  chooseZoomForSpan,
  destinationPoint,
  globalPixelToLonlat,
  haversineDistanceM,
  lonlatToGlobalPixel,
  metersPerPixel,
  type LatLon,
} from "./geometry";

const PRAGUE: LatLon = { lat: 50.0755, lon: 14.4378 };

describe("destinationPoint / bearingBetween / haversineDistanceM", () => {
  it.each([
    [0, 5000],
    [45, 10000],
    [123.5, 3000],
    [270, 8000],
    [359.9, 1500],
  ])("round-trips azimuth %s° over %s m", (azimuth, distance) => {
    const dest = destinationPoint(PRAGUE, azimuth, distance);
    expect(bearingBetween(PRAGUE, dest)).toBeCloseTo(azimuth % 360, 3);
    expect(haversineDistanceM(PRAGUE, dest)).toBeCloseTo(distance, 3);
  });

  it("normalises out-of-range azimuths", () => {
    const a = destinationPoint(PRAGUE, 45, 1000);
    const b = destinationPoint(PRAGUE, 405, 1000);
    expect(haversineDistanceM(a, b)).toBeLessThan(1e-6);
  });

  it("keeps longitude in (-180, 180]", () => {
    const nearDateline: LatLon = { lat: 0, lon: 179.99 };
    const crossed = destinationPoint(nearDateline, 90, 5000);
    expect(crossed.lon).toBeGreaterThan(-180);
    expect(crossed.lon).toBeLessThanOrEqual(180);
  });
});

describe("Web Mercator helpers", () => {
  it("gives a sane ground resolution", () => {
    // ~4.8 m/px at the equator at zoom 15.
    expect(metersPerPixel(0, 15)).toBeGreaterThan(3);
    expect(metersPerPixel(0, 15)).toBeLessThan(6);
    // Coarser toward the poles for the same zoom.
    expect(metersPerPixel(60, 15)).toBeLessThan(metersPerPixel(0, 15));
    // Each zoom level halves it.
    expect(metersPerPixel(0, 16)).toBeCloseTo(metersPerPixel(0, 15) / 2, 6);
  });

  it("round-trips lat/lon through pixel space", () => {
    for (const zoom of [10, 15, 19]) {
      const [x, y] = lonlatToGlobalPixel(PRAGUE, zoom);
      const back = globalPixelToLonlat(x, y, zoom);
      expect(back.lat).toBeCloseTo(PRAGUE.lat, 9);
      expect(back.lon).toBeCloseTo(PRAGUE.lon, 9);
    }
  });
});

describe("chooseZoomForSpan", () => {
  it("covers twice the requested distance, as tightly as possible", () => {
    const distance = 2000;
    const zoom = chooseZoomForSpan(distance, PRAGUE.lat, 640);
    expect(metersPerPixel(PRAGUE.lat, zoom) * 640).toBeGreaterThanOrEqual(2 * distance);
    if (zoom < 20) {
      expect(metersPerPixel(PRAGUE.lat, zoom + 1) * 640).toBeLessThan(2 * distance);
    }
  });
});
