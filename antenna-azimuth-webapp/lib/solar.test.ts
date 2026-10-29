import { describe, expect, it } from "vitest";

import { solarPosition } from "./solar";

const PRAGUE = { lat: 50.0755, lon: 14.4378 };

describe("solarPosition", () => {
  it("stays within physical bounds", () => {
    for (let hour = 0; hour < 24; hour += 3) {
      const pos = solarPosition(PRAGUE.lat, PRAGUE.lon, new Date(Date.UTC(2026, 5, 21, hour)));
      expect(pos.elevationDeg).toBeGreaterThanOrEqual(-90);
      expect(pos.elevationDeg).toBeLessThanOrEqual(90);
      expect(pos.azimuthDeg).toBeGreaterThanOrEqual(0);
      expect(pos.azimuthDeg).toBeLessThan(360);
    }
  });

  it("puts the midsummer noon sun high and to the south", () => {
    // Solar noon in Prague (14.44°E) is around 11:02 UTC.
    const pos = solarPosition(PRAGUE.lat, PRAGUE.lon, new Date("2026-06-21T11:00:00Z"));
    expect(pos.elevationDeg).toBeGreaterThan(60);
    expect(pos.azimuthDeg).toBeGreaterThan(150);
    expect(pos.azimuthDeg).toBeLessThan(210);
  });

  it("puts the midwinter noon sun low and still to the south", () => {
    const pos = solarPosition(PRAGUE.lat, PRAGUE.lon, new Date("2026-12-21T11:00:00Z"));
    expect(pos.elevationDeg).toBeGreaterThan(10);
    expect(pos.elevationDeg).toBeLessThan(20);
    expect(pos.azimuthDeg).toBeGreaterThan(150);
    expect(pos.azimuthDeg).toBeLessThan(210);
  });

  it("tracks east to west across the day", () => {
    const day = "2026-03-20";
    const morning = solarPosition(PRAGUE.lat, PRAGUE.lon, new Date(`${day}T07:00:00Z`));
    const noon = solarPosition(PRAGUE.lat, PRAGUE.lon, new Date(`${day}T11:00:00Z`));
    const afternoon = solarPosition(PRAGUE.lat, PRAGUE.lon, new Date(`${day}T16:00:00Z`));
    expect(morning.azimuthDeg).toBeLessThan(noon.azimuthDeg);
    expect(noon.azimuthDeg).toBeLessThan(afternoon.azimuthDeg);
    expect(noon.elevationDeg).toBeGreaterThan(morning.elevationDeg);
    expect(noon.elevationDeg).toBeGreaterThan(afternoon.elevationDeg);
  });

  it("puts the sun below the horizon at local midnight", () => {
    const pos = solarPosition(PRAGUE.lat, PRAGUE.lon, new Date("2026-06-21T23:00:00Z"));
    expect(pos.elevationDeg).toBeLessThan(0);
  });

  it("sees the southern hemisphere's noon sun to the north", () => {
    // Sydney, local noon ≈ 01:00 UTC.
    const pos = solarPosition(-33.87, 151.21, new Date("2026-06-21T02:00:00Z"));
    expect(pos.elevationDeg).toBeGreaterThan(0);
    expect(pos.azimuthDeg > 330 || pos.azimuthDeg < 30).toBe(true);
  });
});
