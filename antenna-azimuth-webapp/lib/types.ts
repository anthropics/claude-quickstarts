import type { LatLon } from "./geometry";

/**
 * A target picked off the imagery rather than entered as a bearing.
 *
 * `apparent` is where the feature *looks* like it is; if it stands above the
 * ground its image position is displaced by the satellite's viewing angle,
 * which is what `lib/relief.ts` undoes given `heightM`.
 */
export interface RayTarget {
  apparent: LatLon;
  /** Height above ground of the picked feature (mast top, rooftop antenna). */
  heightM: number;
}

export interface AzimuthRay {
  id: string;
  label: string;
  /** Manually entered bearing. Ignored while `target` is set. */
  azimuthDeg: number;
  distanceM: number;
  beamwidthDeg: number | null;
  /** When set, the bearing is derived from this point and relief-corrected. */
  target?: RayTarget;
}

/**
 * Result of probing the imagery for a shadow near a point.
 *
 * This measures a *reference object* so its height can be fed into the
 * imagery calibration — it is not a statement about obstructions on the path.
 */
export interface ShadowProbeResponse {
  found: boolean;
  shadowAzimuthDeg?: number;
  /** How far the shadow's direction sits from the astronomically expected one. */
  angularErrorDeg?: number;
  shadowLengthM?: number;
  /** Height of the object that cast it — the input the calibration needs. */
  referenceHeightM?: number | null;
  confidence?: "low" | "medium" | "high";
  shadowLocation?: LatLon;
  sun: { azimuthDeg: number; elevationDeg: number };
  captureDatetime: string;
  error?: string;
}

export const RAY_COLORS = ["#ff6a3d", "#3ea1ff", "#ffd23f", "#3ddc84", "#c792ff"];
