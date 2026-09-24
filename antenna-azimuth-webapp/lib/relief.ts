/**
 * Relief-displacement correction — the actual "angle the satellite shot from"
 * effect on measured azimuths.
 *
 * WHAT IS AND ISN'T DISTORTED
 *
 * A satellite basemap and a vector basemap are both Web Mercator, north-up,
 * on the same tile grid, and a bearing here is computed from latitude and
 * longitude rather than from pixels. So for two points **on the ground** the
 * azimuth is identical on either layer — there is nothing to correct.
 *
 * What genuinely is displaced is anything standing *above* the ground.
 * Orthorectification places the terrain correctly using a bare-earth model,
 * but a mast, a rooftop or a chimney is not in that model: its top is imaged
 * along the slanted line of sight to the satellite and therefore lands away
 * from its true ground position, by
 *
 *     d = h · cot(E_sat)      along bearing   A_sat + 180°
 *
 * where `h` is height above ground and `E_sat` / `A_sat` are the satellite's
 * elevation and azimuth as seen from the object. Picking an antenna link's
 * far end by its mast top — the normal way to pick it — therefore yields a
 * bearing that is off. At 30 m height and 30° off-nadir the displacement is
 * about 17 m: ~2° of azimuth error at 500 m, ~5° at 200 m, and asymptotically
 * nothing at long range.
 *
 * HOW SHADOWS SOLVE IT
 *
 * `E_sat` and `A_sat` are not published per tile, but they can be recovered
 * from the image itself, because a shadow and a lean are the same radial
 * geometry with the sun swapped for the satellite:
 *
 *     shadow:  L_shadow = h · cot(E_sun),  bearing A_sun + 180°
 *     lean:    L_lean   = h · cot(E_sat),  bearing A_sat + 180°
 *
 * The sun's position is computed astronomically (`lib/solar.ts`), so a
 * measured shadow gives `h`; with `h` known, the object's measured lean gives
 * the satellite geometry. One reference object is enough to calibrate the
 * imagery patch it sits in.
 */

import {
  bearingBetween,
  destinationPoint,
  haversineDistanceM,
  type LatLon,
} from "./geometry";

const DEG = Math.PI / 180;

/**
 * Imagery viewing geometry, recovered from one reference object.
 *
 * `leanPerMetre` is `cot(E_sat)` — metres of displacement per metre of
 * height — which is the form the correction actually needs and the form
 * that can be shown to a user without trigonometry ("leans 0.58 m per metre
 * of height, toward 47°").
 */
export interface ImageryCalibration {
  leanPerMetre: number;
  /** Bearing along which tops are displaced, i.e. away from the satellite. */
  displacementBearingDeg: number;
  satelliteElevationDeg: number;
  satelliteAzimuthDeg: number;
  /** Height of the reference object the calibration was derived from. */
  referenceHeightM: number;
}

export interface AzimuthCorrection {
  /** Bearing to the point as picked, i.e. to the displaced image position. */
  rawDeg: number;
  /** Bearing to the target's true ground position. */
  correctedDeg: number;
  /** Signed difference, corrected − raw, normalised to (−180, 180]. */
  deltaDeg: number;
  correctedTarget: LatLon;
}

function normalizeBearing(deg: number): number {
  return ((deg % 360) + 360) % 360;
}

/** Signed difference b − a, normalised to (−180, 180]. */
export function bearingDeltaDeg(a: number, b: number): number {
  const d = ((b - a + 540) % 360) - 180;
  // (−180, 180] rather than [−180, 180): keep +180 rather than −180.
  return d === -180 ? 180 : d;
}

/**
 * Height of a vertical object from the length of its shadow.
 *
 * Undefined below a few degrees of sun elevation, where the shadow runs
 * essentially to the horizon and length stops constraining height.
 */
export function heightFromShadow(
  shadowLengthM: number,
  sunElevationDeg: number,
  minSunElevationDeg = 5
): number | null {
  if (sunElevationDeg <= minSunElevationDeg) return null;
  return shadowLengthM * Math.tan(sunElevationDeg * DEG);
}

/**
 * Recover the imagery's viewing geometry from a reference object whose base
 * and apparent top are both identifiable in the image.
 *
 * `base` → `top` is the observed lean: its bearing points away from the
 * satellite, its length is `h · cot(E_sat)`.
 *
 * Returns null when the two points coincide (nothing to measure) or the
 * height is non-positive.
 */
export function calibrateFromReference(params: {
  base: LatLon;
  top: LatLon;
  heightM: number;
}): ImageryCalibration | null {
  const { base, top, heightM } = params;
  if (!(heightM > 0)) return null;

  const leanM = haversineDistanceM(base, top);
  if (leanM <= 0) return null;

  const displacementBearingDeg = bearingBetween(base, top);
  const leanPerMetre = leanM / heightM;

  return {
    leanPerMetre,
    displacementBearingDeg,
    satelliteElevationDeg: Math.atan2(heightM, leanM) / DEG,
    satelliteAzimuthDeg: normalizeBearing(displacementBearingDeg + 180),
    referenceHeightM: heightM,
  };
}

/**
 * Map an apparent (as-picked) image position of a point `heightM` above
 * ground back to its true ground position, by undoing the lean.
 */
export function correctApparentPosition(
  apparent: LatLon,
  heightM: number,
  calibration: ImageryCalibration
): LatLon {
  if (!(heightM > 0)) return apparent;
  const displacementM = heightM * calibration.leanPerMetre;
  if (displacementM <= 0) return apparent;
  // Walk back toward the satellite, i.e. opposite the displacement bearing.
  return destinationPoint(
    apparent,
    calibration.displacementBearingDeg + 180,
    displacementM
  );
}

/**
 * Bearing from `origin` to a target picked at its apparent image position,
 * before and after undoing the target's lean.
 *
 * `origin` is assumed to be a true ground position — it comes from GPS, or
 * from a marker the user placed on the ground rather than on a rooftop.
 */
export function correctedAzimuth(
  origin: LatLon,
  apparentTarget: LatLon,
  targetHeightM: number,
  calibration: ImageryCalibration | null
): AzimuthCorrection {
  const rawDeg = bearingBetween(origin, apparentTarget);
  if (!calibration || !(targetHeightM > 0)) {
    return { rawDeg, correctedDeg: rawDeg, deltaDeg: 0, correctedTarget: apparentTarget };
  }

  const correctedTarget = correctApparentPosition(apparentTarget, targetHeightM, calibration);
  const correctedDeg = bearingBetween(origin, correctedTarget);

  return {
    rawDeg,
    correctedDeg,
    deltaDeg: bearingDeltaDeg(rawDeg, correctedDeg),
    correctedTarget,
  };
}

/**
 * Magnitude of the azimuth error a target of this height would suffer at this
 * range, without needing a concrete target position.
 *
 * Used by the UI to say "at this distance the correction is worth about X°",
 * and to justify not bothering past a few kilometres. Worst case: the whole
 * displacement lies across the line of sight.
 */
export function maxAzimuthErrorDeg(
  targetHeightM: number,
  distanceM: number,
  calibration: ImageryCalibration | null
): number {
  if (!calibration || !(targetHeightM > 0) || !(distanceM > 0)) return 0;
  const displacementM = targetHeightM * calibration.leanPerMetre;
  return Math.asin(Math.min(1, displacementM / distanceM)) / DEG;
}
