/**
 * Heuristic shadow-blob detection — server-only (operates on a raw RGB pixel
 * buffer from tiles.ts). Ported from
 * antenna-azimuth-mapper/azimuth_mapper/{shadow_detect,correction}.py.
 *
 * Purpose: measure a *reference object's* shadow so its height can be
 * recovered, because that height is what `lib/relief.ts` needs to turn the
 * object's observed lean into the imagery's satellite viewing geometry. The
 * height is an intermediate quantity for calibrating azimuth corrections —
 * it is not a claim about obstructions along a path.
 *
 * There's no OpenCV here, so this reimplements the same pipeline shape by
 * hand: grayscale -> Otsu threshold -> morphological open/close -> connected
 * components -> PCA orientation per blob. Two deliberate simplifications
 * versus the Python/OpenCV version, both fine for a heuristic: (1) area and
 * orientation are computed from every filled pixel in a blob rather than
 * just its boundary contour, and (2) the oriented bounding extent is
 * computed by projecting onto the PCA axes rather than a true
 * minimum-area rotated rect — for the elongated, roughly-rectangular blobs
 * shadows produce, both track the OpenCV originals closely.
 *
 * What's computable here without per-tile sensor metadata: shadow length in
 * the image, combined with the astronomically-true sun elevation for the
 * place/time, gives the reference object's height. The satellite's viewing
 * geometry does *not* follow from a shadow alone — that needs the object's
 * lean as well, which the user marks in the UI and `lib/relief.ts` solves.
 *
 * Performance note: this runs per request on a serverless function over a
 * 512x512 crop, so the pipeline is written to avoid per-pixel allocation —
 * see `morphOpen`/`morphClose` (separable passes over reused buffers) and
 * `connectedComponents` (flat pixel indices in one array, no point objects).
 */
import { heightFromShadow } from "./relief";
import type { SolarPosition } from "./solar";

const MIN_BLOB_AREA_PX = 25;
const MIN_ELONGATION = 2.0;
const MIN_SUN_ELEVATION_FOR_HEIGHT_DEG = 5.0;
const MAX_AXIS_ANGULAR_ERROR_DEG = 45.0;

export interface ShadowObservation {
  centroidPx: [number, number];
  /** One of the two 180-degree-apart candidate directions, compass bearing. */
  axisDegA: number;
  axisDegB: number;
  lengthPx: number;
  areaPx: number;
  distanceFromOriginPx: number;
}

export interface ShadowEstimate {
  /** Resolved direction, object base -> shadow tip. */
  shadowAzimuthDeg: number;
  /** Distance from the astronomically-expected shadow direction. */
  angularErrorDeg: number;
  shadowLengthM: number;
  /** Height of the object that cast it; feeds the imagery calibration. */
  referenceHeightM: number | null;
  confidence: "low" | "medium" | "high";
  centroidPx: [number, number];
}

/**
 * Threshold straight to a 0/1 mask, fusing grayscale conversion, the Otsu
 * histogram and the comparison into two passes over the pixels.
 *
 * Luma uses the same integer weights OpenCV's cv2.COLOR_RGB2GRAY applies
 * (0.299/0.587/0.114 in Q8 fixed point), so the threshold lands on the same
 * bucket the Python version would pick.
 */
function thresholdMask(raw: Buffer, width: number, height: number): Uint8Array {
  const n = width * height;
  const gray = new Uint8Array(n);
  const hist = new Int32Array(256);

  for (let i = 0, p = 0; i < n; i++, p += 3) {
    const v = (77 * raw[p] + 150 * raw[p + 1] + 29 * raw[p + 2] + 128) >> 8;
    gray[i] = v;
    hist[v]++;
  }

  let sum = 0;
  for (let t = 0; t < 256; t++) sum += t * hist[t];

  let sumB = 0;
  let wB = 0;
  let maxVariance = -1;
  let threshold = 0;
  for (let t = 0; t < 256; t++) {
    wB += hist[t];
    if (wB === 0) continue;
    const wF = n - wB;
    if (wF === 0) break;
    sumB += t * hist[t];
    const meanDiff = sumB / wB - (sum - sumB) / wF;
    const variance = wB * wF * meanDiff * meanDiff;
    if (variance > maxVariance) {
      maxVariance = variance;
      threshold = t;
    }
  }

  const mask = new Uint8Array(n);
  for (let i = 0; i < n; i++) mask[i] = gray[i] <= threshold ? 1 : 0;
  return mask;
}

/**
 * One separable 3x3 morphology pass over a binary mask, out-of-bounds
 * treated as 0. A 3x3 rectangular structuring element is separable, so the
 * horizontal and vertical halves give exactly the same result as the naive
 * 9-neighbour scan while touching a third of the memory.
 *
 * `erode` is a min filter (AND), `dilate` a max filter (OR); on a 0/1 mask
 * those are just bitwise ops. Both buffers are caller-owned and reused
 * across passes so a full open+close allocates nothing.
 */
function morphPass(
  src: Uint8Array,
  dst: Uint8Array,
  scratch: Uint8Array,
  width: number,
  height: number,
  erode: boolean
): void {
  // Horizontal.
  for (let y = 0; y < height; y++) {
    const row = y * width;
    for (let x = 0; x < width; x++) {
      const i = row + x;
      const left = x > 0 ? src[i - 1] : 0;
      const right = x < width - 1 ? src[i + 1] : 0;
      scratch[i] = erode ? left & src[i] & right : left | src[i] | right;
    }
  }

  // Vertical.
  const last = height - 1;
  for (let y = 0; y < height; y++) {
    const row = y * width;
    const up = y > 0 ? row - width : -1;
    const down = y < last ? row + width : -1;
    for (let x = 0; x < width; x++) {
      const i = row + x;
      const a = up >= 0 ? scratch[up + x] : 0;
      const b = down >= 0 ? scratch[down + x] : 0;
      dst[i] = erode ? a & scratch[i] & b : a | scratch[i] | b;
    }
  }
}

interface ComponentRange {
  start: number;
  length: number;
}

/**
 * Flood-fill every set region, writing member pixels as flat indices into a
 * single array and returning (start, length) ranges into it.
 *
 * The output array doubles as the BFS queue — each component's own slice is
 * filled front-to-back while being read front-to-back — so labelling a whole
 * image allocates one Int32Array rather than one small array per pixel.
 */
function connectedComponents(
  mask: Uint8Array,
  width: number,
  height: number
): { pixels: Int32Array; ranges: ComponentRange[] } {
  const n = width * height;
  const visited = new Uint8Array(n);
  const pixels = new Int32Array(n);
  const ranges: ComponentRange[] = [];
  let write = 0;

  for (let seed = 0; seed < n; seed++) {
    if (mask[seed] !== 1 || visited[seed] === 1) continue;

    const start = write;
    visited[seed] = 1;
    pixels[write++] = seed;

    for (let read = start; read < write; read++) {
      const idx = pixels[read];
      const x = idx % width;
      const y = (idx / width) | 0;

      const xMin = x > 0 ? -1 : 0;
      const xMax = x < width - 1 ? 1 : 0;
      const yMin = y > 0 ? -1 : 0;
      const yMax = y < height - 1 ? 1 : 0;

      for (let dy = yMin; dy <= yMax; dy++) {
        const row = idx + dy * width;
        for (let dx = xMin; dx <= xMax; dx++) {
          if (dx === 0 && dy === 0) continue;
          const nIdx = row + dx;
          if (mask[nIdx] === 1 && visited[nIdx] === 0) {
            visited[nIdx] = 1;
            pixels[write++] = nIdx;
          }
        }
      }
    }

    ranges.push({ start, length: write - start });
  }

  return { pixels, ranges };
}

/** PCA principal axis + oriented extent of one component, read in place. */
function principalAxis(
  pixels: Int32Array,
  start: number,
  length: number,
  width: number
) {
  const end = start + length;

  let sx = 0;
  let sy = 0;
  for (let i = start; i < end; i++) {
    const idx = pixels[i];
    sx += idx % width;
    sy += (idx / width) | 0;
  }
  const cx = sx / length;
  const cy = sy / length;

  let cxx = 0;
  let cyy = 0;
  let cxy = 0;
  for (let i = start; i < end; i++) {
    const idx = pixels[i];
    const dx = (idx % width) - cx;
    const dy = ((idx / width) | 0) - cy;
    cxx += dx * dx;
    cyy += dy * dy;
    cxy += dx * dy;
  }
  cxx /= length;
  cyy /= length;
  cxy /= length;

  const trace = cxx + cyy;
  const det = cxx * cyy - cxy * cxy;
  const disc = Math.sqrt(Math.max(0, (trace * trace) / 4 - det));
  const lambdaMajor = trace / 2 + disc;

  let vx: number;
  let vy: number;
  if (Math.abs(cxy) > 1e-9) {
    vx = lambdaMajor - cyy;
    vy = cxy;
  } else if (cxx >= cyy) {
    vx = 1;
    vy = 0;
  } else {
    vx = 0;
    vy = 1;
  }
  const norm = Math.hypot(vx, vy) || 1;
  vx /= norm;
  vy /= norm;
  // Perpendicular (minor) axis.
  const mvx = -vy;
  const mvy = vx;

  let majorMin = Infinity;
  let majorMax = -Infinity;
  let minorMin = Infinity;
  let minorMax = -Infinity;
  for (let i = start; i < end; i++) {
    const idx = pixels[i];
    const dx = (idx % width) - cx;
    const dy = ((idx / width) | 0) - cy;
    const projMajor = dx * vx + dy * vy;
    const projMinor = dx * mvx + dy * mvy;
    if (projMajor < majorMin) majorMin = projMajor;
    if (projMajor > majorMax) majorMax = projMajor;
    if (projMinor < minorMin) minorMin = projMinor;
    if (projMinor > minorMax) minorMax = projMinor;
  }

  // Image space: x right, y down. Compass bearing: 0 = up (north), clockwise.
  const angleDeg = (((Math.atan2(vx, -vy) * 180) / Math.PI) % 360 + 360) % 360;

  return {
    centroid: [cx, cy] as [number, number],
    majorLen: majorMax - majorMin,
    minorLen: minorMax - minorMin,
    axisDegA: angleDeg,
    axisDegB: (angleDeg + 180) % 360,
  };
}

export function detectShadows(
  raw: Buffer,
  width: number,
  height: number,
  originPx: [number, number]
): ShadowObservation[] {
  const n = width * height;
  const mask = thresholdMask(raw, width, height);

  // Open (erode -> dilate) then close (dilate -> erode), ping-ponging between
  // two buffers plus one scratch row-buffer shared by every separable pass.
  const buffer = new Uint8Array(n);
  const scratch = new Uint8Array(n);
  morphPass(mask, buffer, scratch, width, height, true); // erode
  morphPass(buffer, mask, scratch, width, height, false); // dilate  -> open, in mask
  morphPass(mask, buffer, scratch, width, height, false); // dilate
  morphPass(buffer, mask, scratch, width, height, true); // erode   -> close, in mask

  const { pixels, ranges } = connectedComponents(mask, width, height);
  const [ox, oy] = originPx;

  const observations: ShadowObservation[] = [];
  for (const { start, length } of ranges) {
    if (length < MIN_BLOB_AREA_PX) continue;

    const { centroid, majorLen, minorLen, axisDegA, axisDegB } = principalAxis(
      pixels,
      start,
      length,
      width
    );
    if (majorLen / Math.max(minorLen, 1e-6) < MIN_ELONGATION) continue;

    observations.push({
      centroidPx: centroid,
      axisDegA,
      axisDegB,
      lengthPx: majorLen,
      areaPx: length,
      distanceFromOriginPx: Math.hypot(centroid[0] - ox, centroid[1] - oy),
    });
  }

  observations.sort((a, b) => a.distanceFromOriginPx - b.distanceFromOriginPx);
  return observations;
}

function angularDiff(a: number, b: number): number {
  const d = Math.abs(a - b) % 360;
  return Math.min(d, 360 - d);
}

export function estimateFromShadow(
  obs: ShadowObservation,
  sun: SolarPosition,
  metersPerPx: number
): ShadowEstimate | null {
  const expectedShadowAzimuth = (sun.azimuthDeg + 180) % 360;
  const errA = angularDiff(obs.axisDegA, expectedShadowAzimuth);
  const errB = angularDiff(obs.axisDegB, expectedShadowAzimuth);
  const [shadowAzimuthDeg, angularErrorDeg] = errA <= errB ? [obs.axisDegA, errA] : [obs.axisDegB, errB];

  if (sun.elevationDeg <= 0 || angularErrorDeg > MAX_AXIS_ANGULAR_ERROR_DEG) {
    return null;
  }

  const shadowLengthM = obs.lengthPx * metersPerPx;
  const referenceHeightM = heightFromShadow(
    shadowLengthM,
    sun.elevationDeg,
    MIN_SUN_ELEVATION_FOR_HEIGHT_DEG
  );

  let confidence: ShadowEstimate["confidence"];
  if (angularErrorDeg < 10 && obs.areaPx > 60) confidence = "high";
  else if (angularErrorDeg < 25) confidence = "medium";
  else confidence = "low";

  return {
    shadowAzimuthDeg,
    angularErrorDeg,
    shadowLengthM,
    referenceHeightM,
    confidence,
    centroidPx: obs.centroidPx,
  };
}

/** Nearest-to-origin candidate first; returns the first one that looks like a real shadow. */
export function bestEstimate(
  observations: ShadowObservation[],
  sun: SolarPosition,
  metersPerPx: number
): ShadowEstimate | null {
  for (const obs of observations) {
    const estimate = estimateFromShadow(obs, sun, metersPerPx);
    if (estimate !== null) return estimate;
  }
  return null;
}
