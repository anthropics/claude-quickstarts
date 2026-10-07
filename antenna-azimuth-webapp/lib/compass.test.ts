import { describe, expect, it } from "vitest";
import { compassHeading, type CompassSample } from "./compass";

const flat: CompassSample = { alpha: 90, beta: 0, gamma: 0, absolute: true };
describe("phone compass", () => {
  it("uses the iPhone compass heading rather than relative alpha", () => {
    expect(compassHeading({ ...flat, absolute: false, webkitCompassHeading: 45, webkitCompassAccuracy: 5 }, 0)).toBe(45);
  });
  it("converts an absolute Android orientation", () => {
    expect(compassHeading(flat, 0)).toBe(270);
    expect(compassHeading({ ...flat, alpha: 360 }, 0)).toBe(0);
  });
  it("does not pretend relative orientation is a compass", () => {
    expect(compassHeading({ ...flat, absolute: false }, 0)).toBeNull();
  });
  it("rejects an uncalibrated sensor, tilted phone and landscape orientation", () => {
    expect(compassHeading({ ...flat, webkitCompassHeading: 90, webkitCompassAccuracy: -1 }, 0)).toBeNull();
    expect(compassHeading({ ...flat, beta: 60 }, 0)).toBeNull();
    expect(compassHeading(flat, 90)).toBeNull();
  });
  it("rejects missing or non-finite values", () => {
    expect(compassHeading({ ...flat, alpha: null }, 0)).toBeNull();
    expect(compassHeading({ ...flat, alpha: NaN }, 0)).toBeNull();
    expect(compassHeading({ ...flat, gamma: NaN }, 0)).toBeNull();
  });
});
