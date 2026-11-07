/**
 * Low-precision solar position (Michalsky/NOAA-style), no external
 * dependencies. Ported 1:1 from
 * antenna-azimuth-mapper/azimuth_mapper/solar.py.
 *
 * Accurate to roughly 0.01 deg for 1950-2050 — far more than this tool
 * needs: it only sanity-checks a shadow direction detected in an image,
 * not anything safety-critical.
 */

export interface SolarPosition {
  azimuthDeg: number; // compass bearing of the sun, 0 = north, clockwise
  elevationDeg: number; // angle above the horizon
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

function toDeg(rad: number): number {
  return (rad * 180) / Math.PI;
}

function mod360(deg: number): number {
  return ((deg % 360) + 360) % 360;
}

const JD_2000_EPOCH_MS = Date.UTC(2000, 0, 1, 12, 0, 0); // JD 2451545.0

function julianDay(dtUtc: Date): number {
  return 2451545.0 + (dtUtc.getTime() - JD_2000_EPOCH_MS) / 86_400_000;
}

/** Sun azimuth/elevation as seen from (lat, lon) at the given UTC instant. */
export function solarPosition(latDeg: number, lonDeg: number, dtUtc: Date): SolarPosition {
  const jd = julianDay(dtUtc);
  const n = jd - 2451545.0;

  const meanLon = toRad(mod360(280.46 + 0.9856474 * n));
  const meanAnomaly = toRad(mod360(357.528 + 0.9856003 * n));
  const eclipticLon =
    meanLon + toRad(1.915 * Math.sin(meanAnomaly) + 0.02 * Math.sin(2 * meanAnomaly));
  const obliquity = toRad(23.439 - 0.0000004 * n);

  const rightAscension = Math.atan2(
    Math.cos(obliquity) * Math.sin(eclipticLon),
    Math.cos(eclipticLon)
  );
  const declination = Math.asin(Math.sin(obliquity) * Math.sin(eclipticLon));

  const gmstDeg = mod360(280.46061837 + 360.98564736629 * n);
  let hourAngleDeg = mod360(gmstDeg + lonDeg - toDeg(rightAscension));
  if (hourAngleDeg > 180) hourAngleDeg -= 360;
  const hourAngle = toRad(hourAngleDeg);

  const lat = toRad(latDeg);
  let sinElevation =
    Math.sin(lat) * Math.sin(declination) +
    Math.cos(lat) * Math.cos(declination) * Math.cos(hourAngle);
  sinElevation = Math.max(-1.0, Math.min(1.0, sinElevation));
  const elevation = Math.asin(sinElevation);

  const denom = Math.cos(lat) * Math.cos(elevation);
  let cosAzimuth =
    Math.abs(denom) > 1e-9
      ? (Math.sin(declination) - Math.sin(lat) * sinElevation) / denom
      : 0.0;
  cosAzimuth = Math.max(-1.0, Math.min(1.0, cosAzimuth));
  let azimuthDeg = toDeg(Math.acos(cosAzimuth));
  if (Math.sin(hourAngle) > 0) azimuthDeg = 360 - azimuthDeg;

  return { azimuthDeg: mod360(azimuthDeg), elevationDeg: toDeg(elevation) };
}
