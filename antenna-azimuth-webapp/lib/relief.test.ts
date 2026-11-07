import { describe, expect, it } from "vitest";

import { bearingBetween, destinationPoint, haversineDistanceM, type LatLon } from "./geometry";
import {
  bearingDeltaDeg,
  calibrateFromReference,
  correctApparentPosition,
  correctedAzimuth,
  heightFromShadow,
  maxAzimuthErrorDeg,
} from "./relief";

const ORIGIN: LatLon = { lat: 50.0755, lon: 14.4378 };
const DEG = Math.PI / 180;

/**
 * Build the reference measurement an image would show for a known satellite
 * geometry, so the tests exercise the recovery rather than restating it: a
 * top displaced from its base by h·cot(E_sat) along A_sat + 180°.
 */
function syntheticReference(base: LatLon, heightM: number, satElevDeg: number, satAzDeg: number) {
  const leanM = heightM / Math.tan(satElevDeg * DEG);
  return destinationPoint(base, satAzDeg + 180, leanM);
}

describe("heightFromShadow", () => {
  it("inverts the shadow-length relation", () => {
    // A 20 m object with the sun 40° up casts 20/tan(40°) ≈ 23.8 m of shadow.
    const shadow = 20 / Math.tan(40 * DEG);
    expect(heightFromShadow(shadow, 40)).toBeCloseTo(20, 6);
  });

  it("refuses to answer with the sun near the horizon", () => {
    expect(heightFromShadow(500, 3)).toBeNull();
    expect(heightFromShadow(500, 0)).toBeNull();
    expect(heightFromShadow(500, -10)).toBeNull();
  });
});

describe("calibrateFromReference", () => {
  it("recovers the satellite geometry that produced a lean", () => {
    const height = 30;
    const satElev = 60;
    const satAz = 130;
    const top = syntheticReference(ORIGIN, height, satElev, satAz);

    const cal = calibrateFromReference({ base: ORIGIN, top, heightM: height })!;
    expect(cal).not.toBeNull();

    // cot(60°) ≈ 0.5774 m of displacement per metre of height.
    expect(cal.leanPerMetre).toBeCloseTo(1 / Math.tan(satElev * DEG), 4);
    expect(cal.satelliteElevationDeg).toBeCloseTo(satElev, 3);
    expect(cal.satelliteAzimuthDeg).toBeCloseTo(satAz, 3);
    expect(cal.displacementBearingDeg).toBeCloseTo((satAz + 180) % 360, 3);
    expect(cal.referenceHeightM).toBe(height);
  });

  it("rejects degenerate input", () => {
    expect(calibrateFromReference({ base: ORIGIN, top: ORIGIN, heightM: 30 })).toBeNull();
    expect(
      calibrateFromReference({ base: ORIGIN, top: syntheticReference(ORIGIN, 10, 60, 0), heightM: 0 })
    ).toBeNull();
  });
});

describe("correctApparentPosition", () => {
  it("undoes the displacement it was calibrated on", () => {
    const height = 30;
    const top = syntheticReference(ORIGIN, height, 60, 130);
    const cal = calibrateFromReference({ base: ORIGIN, top, heightM: height })!;

    // Walking the reference's own top back must land on its base.
    const recovered = correctApparentPosition(top, height, cal);
    expect(haversineDistanceM(recovered, ORIGIN)).toBeLessThan(0.01);
  });

  it("scales with target height", () => {
    const cal = calibrateFromReference({
      base: ORIGIN,
      top: syntheticReference(ORIGIN, 30, 60, 130),
      heightM: 30,
    })!;
    const apparent = destinationPoint(ORIGIN, 45, 500);

    const shifted10 = haversineDistanceM(apparent, correctApparentPosition(apparent, 10, cal));
    const shifted20 = haversineDistanceM(apparent, correctApparentPosition(apparent, 20, cal));
    expect(shifted20 / shifted10).toBeCloseTo(2, 2);
  });

  it("leaves ground-level points alone", () => {
    const cal = calibrateFromReference({
      base: ORIGIN,
      top: syntheticReference(ORIGIN, 30, 60, 130),
      heightM: 30,
    })!;
    const apparent = destinationPoint(ORIGIN, 45, 500);
    expect(correctApparentPosition(apparent, 0, cal)).toEqual(apparent);
  });
});

describe("correctedAzimuth", () => {
  const cal = calibrateFromReference({
    base: ORIGIN,
    // 30° off-nadir, i.e. 60° elevation; displacement toward bearing 310°.
    top: syntheticReference(ORIGIN, 30, 60, 130),
    heightM: 30,
  })!;

  it("matches the hand-worked magnitudes", () => {
    // 30 m at cot(60°) ≈ 17.3 m of displacement. Put the target where that
    // displacement is fully across the line of sight, so the error is maximal:
    // displacement runs along 310°, so sight along 040° is perpendicular.
    const at500 = correctedAzimuth(ORIGIN, destinationPoint(ORIGIN, 40, 500), 30, cal);
    const at200 = correctedAzimuth(ORIGIN, destinationPoint(ORIGIN, 40, 200), 30, cal);

    expect(Math.abs(at500.deltaDeg)).toBeCloseTo(2, 0);
    expect(Math.abs(at200.deltaDeg)).toBeCloseTo(5, 0);
  });

  it("converges to zero with range", () => {
    const deltas = [200, 500, 2000, 10000].map((d) =>
      Math.abs(correctedAzimuth(ORIGIN, destinationPoint(ORIGIN, 40, d), 30, cal).deltaDeg)
    );
    for (let i = 1; i < deltas.length; i++) expect(deltas[i]).toBeLessThan(deltas[i - 1]);
    expect(deltas.at(-1)!).toBeLessThan(0.2);
  });

  it("is a no-op without calibration or height", () => {
    const target = destinationPoint(ORIGIN, 40, 500);
    const noCal = correctedAzimuth(ORIGIN, target, 30, null);
    expect(noCal.deltaDeg).toBe(0);
    expect(noCal.correctedDeg).toBe(noCal.rawDeg);

    const noHeight = correctedAzimuth(ORIGIN, target, 0, cal);
    expect(noHeight.deltaDeg).toBe(0);
  });

  it("reports a bearing consistent with the corrected target", () => {
    const target = destinationPoint(ORIGIN, 40, 500);
    const c = correctedAzimuth(ORIGIN, target, 30, cal);
    expect(c.correctedDeg).toBeCloseTo(bearingBetween(ORIGIN, c.correctedTarget), 9);
    expect(c.rawDeg).toBeCloseTo(bearingBetween(ORIGIN, target), 9);
  });
});

describe("maxAzimuthErrorDeg", () => {
  it("bounds the observed correction", () => {
    const cal = calibrateFromReference({
      base: ORIGIN,
      top: syntheticReference(ORIGIN, 30, 60, 130),
      heightM: 30,
    })!;

    for (const bearing of [0, 40, 130, 250, 310]) {
      const target = destinationPoint(ORIGIN, bearing, 400);
      const actual = Math.abs(correctedAzimuth(ORIGIN, target, 30, cal).deltaDeg);
      const bound = maxAzimuthErrorDeg(30, 400, cal);
      expect(actual).toBeLessThanOrEqual(bound + 1e-6);
    }
  });

  it("is zero without a calibration", () => {
    expect(maxAzimuthErrorDeg(30, 400, null)).toBe(0);
  });
});

describe("bearingDeltaDeg", () => {
  it("takes the short way around the compass", () => {
    expect(bearingDeltaDeg(10, 20)).toBeCloseTo(10, 9);
    expect(bearingDeltaDeg(20, 10)).toBeCloseTo(-10, 9);
    expect(bearingDeltaDeg(350, 10)).toBeCloseTo(20, 9);
    expect(bearingDeltaDeg(10, 350)).toBeCloseTo(-20, 9);
    expect(bearingDeltaDeg(0, 180)).toBeCloseTo(180, 9);
  });
});
