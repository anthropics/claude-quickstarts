import { describe, expect, it } from "vitest";
import { parseDecimal, validateProject, projectRays, projectIsComplete, type MountingProject } from "./projects";
const project = (): MountingProject => ({
 id: "project", name: "Testovací montáž", siteCode: "TEST", latitude: 50, longitude: 14,
 revision: 1, updatedAt: "2026-10-06T00:00:00.000Z", document: null,
 sectors: [{ id: "a", name: "A", azimuthDeg: 120, mechanicalTiltDeg: null, electricalTiltDeg: 0,
 sourcePage: 1, sourceText: "A 120 — 0", warnings: [] }]
});
describe("confirmed mounting projects", () => {
 it("keeps missing values separate from zero and rejects nonnumeric input", () => {
  expect(parseDecimal("")).toBeNull(); expect(parseDecimal("  ")).toBeNull();
  expect(parseDecimal("0")).toBe(0); expect(parseDecimal("-2,5")).toBe(-2.5);
  expect(parseDecimal("Infinity")).toBeNull(); expect(parseDecimal("4 m")).toBeNull();
 });
 it("maps confirmed bearings and tilts without a picked target", () => {
  const rays = projectRays(project());
  expect(rays[0]).toMatchObject({ azimuthDeg: 120, mechanicalTiltDeg: null, electricalTiltDeg: 0 });
  expect(rays[0].target).toBeUndefined();
 });
 it("rejects incomplete/out-of-range geometry before loading a project", () => {
  const p = project(); p.latitude = null;
  expect(validateProject(p)).not.toEqual([]);
  p.longitude = null; p.sectors[0].azimuthDeg = 360;
  expect(() => projectRays(p)).toThrow();
  p.sectors[0].azimuthDeg = 0; p.sectors[0].mechanicalTiltDeg = 91;
  expect(validateProject(p)).not.toEqual([]);
 });
 it("only moves a project to completed after every sector is explicitly confirmed", () => {
  const p = project();
  expect(projectIsComplete(p)).toBe(false);
  p.sectors[0].completedAt = "2026-10-06T10:00:00Z";
  expect(projectIsComplete(p)).toBe(true);
  p.sectors.push({ ...p.sectors[0], id: "b", completedAt: null });
  expect(projectIsComplete(p)).toBe(false);
  p.sectors[1].completedAt = "not a date";
  expect(projectIsComplete(p)).toBe(false);
  p.sectors = [];
  expect(projectIsComplete(p)).toBe(false);
 });
});
