import type { AzimuthRay } from "./types";

export interface ProjectSector {
  id: string;
  name: string;
  azimuthDeg: number | null;
  mechanicalTiltDeg: number | null;
  electricalTiltDeg: number | null;
  sourcePage: number | null;
  sourceText: string;
  warnings: string[];
  completedAt?: string | null;
}

export interface MountingProject {
  id: string;
  name: string;
  siteCode: string;
  latitude: number | null;
  longitude: number | null;
  sectors: ProjectSector[];
  document: { name: string; path: string; sha256: string } | null;
  revision: number;
  updatedAt: string;
}

export function emptySector(): ProjectSector {
  return { id: crypto.randomUUID(), name: "", azimuthDeg: null, mechanicalTiltDeg: null,
    electricalTiltDeg: null, sourcePage: null, sourceText: "", warnings: [] };
}

export function emptyProject(): MountingProject {
  return { id: crypto.randomUUID(), name: "", siteCode: "", latitude: null, longitude: null,
    sectors: [], document: null, revision: 0, updatedAt: new Date().toISOString() };
}

export function parseDecimal(value: string): number | null {
  const text = value.trim().replace(",", ".");
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return null;
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}

export function validateProject(project: MountingProject): string[] {
  const errors: string[] = [];
  if (!project.name.trim() || project.name.length > 160) errors.push("Vyplňte název projektu (nejvýše 160 znaků).");
  if (project.siteCode.length > 100) errors.push("Kód lokality je příliš dlouhý.");
  if ((project.latitude === null) !== (project.longitude === null)) errors.push("Zadejte obě souřadnice, nebo ponechte obě prázdné.");
  if (project.latitude !== null && (!Number.isFinite(project.latitude) || Math.abs(project.latitude) > 85)) errors.push("Zeměpisná šířka musí být od −85 do 85°.");
  if (project.longitude !== null && (!Number.isFinite(project.longitude) || Math.abs(project.longitude) > 180)) errors.push("Zeměpisná délka musí být od −180 do 180°.");
  if (!project.sectors.length || project.sectors.length > 300) errors.push("Projekt musí mít 1 až 300 položek antén.");
  const ids = new Set<string>();
  project.sectors.forEach((sector, index) => {
    const label = "Řádek " + (index + 1);
    if (ids.has(sector.id)) errors.push(label + ": duplicitní identifikátor.");
    ids.add(sector.id);
    if (!sector.name.trim() || sector.name.length > 160) errors.push(label + ": vyplňte název sektoru nebo antény (nejvýše 160 znaků).");
    if (sector.azimuthDeg === null || !Number.isFinite(sector.azimuthDeg) || sector.azimuthDeg < 0 || sector.azimuthDeg >= 360) errors.push(label + ": azimut musí být od 0 do méně než 360° (sever = 0°).");
    for (const [kind, value] of [["mechanický", sector.mechanicalTiltDeg], ["elektrický", sector.electricalTiltDeg]] as const) {
      if (value !== null && (!Number.isFinite(value) || Math.abs(value) > 90)) errors.push(label + ": " + kind + " náklon musí být od −90 do 90°, nebo prázdný.");
    }
  });
  return errors;
}

/** Confirmed values only. A previous picked target must not override imported bearings. */
export function projectRays(project: MountingProject): AzimuthRay[] {
  const errors = validateProject(project);
  if (errors.length) throw new Error(errors[0]);
  return project.sectors.map((sector) => ({
    id: sector.id, label: sector.name, azimuthDeg: sector.azimuthDeg!, distanceM: 1000,
    beamwidthDeg: null, mechanicalTiltDeg: sector.mechanicalTiltDeg,
    electricalTiltDeg: sector.electricalTiltDeg,
  }));
}

/** Completion is the installer's confirmation, never a compass inference. */
export function projectIsComplete(project: MountingProject): boolean {
  return project.sectors.length > 0 && project.sectors.every(sector => Boolean(sector.completedAt) && Number.isFinite(Date.parse(sector.completedAt!)));
}
