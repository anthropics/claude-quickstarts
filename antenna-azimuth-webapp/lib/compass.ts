export interface CompassSample {
  alpha: number | null;
  beta: number | null;
  gamma: number | null;
  absolute: boolean;
  webkitCompassHeading?: number;
  webkitCompassAccuracy?: number;
}

/** Heading of the top edge, with the phone flat in portrait orientation. */
export function compassHeading(sample: CompassSample, screenAngle: number): number | null {
  if (screenAngle !== 0 || sample.beta == null || sample.gamma == null ||
      !Number.isFinite(sample.beta) || !Number.isFinite(sample.gamma) ||
      Math.abs(sample.beta) > 25 || Math.abs(sample.gamma) > 25) return null;
  const accuracy = sample.webkitCompassAccuracy;
  if (accuracy != null && (!Number.isFinite(accuracy) || accuracy < 0 || accuracy > 30)) return null;
  const heading = sample.webkitCompassHeading;
  if (heading != null && Number.isFinite(heading)) return ((heading % 360) + 360) % 360;
  if (!sample.absolute || sample.alpha == null || !Number.isFinite(sample.alpha)) return null;
  return ((360 - sample.alpha) % 360 + 360) % 360;
}
