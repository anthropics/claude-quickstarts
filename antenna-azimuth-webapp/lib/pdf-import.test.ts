import { describe, expect, it } from "vitest";
import { parseAssignmentPages, type PdfTextItem, type PdfTextPage } from "./pdf-import";

const item = (text: string, x: number, y: number): PdfTextItem => ({ text, x, y });
function tablePage(page: number, rows: string[][], labels = ["Sektor", "Band", "Azimut °", "Mechanický tilt °", "Elektrický tilt °"]): PdfTextPage {
  const xs = [20, 100, 180, 300, 420, 540];
  return { page, items: [
    ...labels.map((label, index) => item(label, xs[index], 700)),
    ...rows.flatMap((row, rowIndex) => row.map((value, index) => item(value, xs[index] + 10, 650 - rowIndex * 14))),
  ] };
}

describe("parseAssignmentPages positioned text (synthetic fixtures, not verified assignments)", () => {
  it("reads Czech sector rows, decimal comma and negative tilt, with page and raw source", () => {
    const result = parseAssignmentPages([tablePage(2, [["A", "1800", "120,5°", "-2,5", "0"]])]);
    expect(result.sectors).toHaveLength(1);
    expect(result.sectors[0]).toMatchObject({
      name: "A / 1800", azimuthDeg: 120.5, mechanicalTiltDeg: -2.5, electricalTiltDeg: 0,
      sourcePage: 2, warnings: [],
    });
    expect(result.sectors[0].sourceText).toContain("120,5°");
    expect(result.sectors[0].sourceText).toContain("-2,5");
  });

  it("recognizes English and compact antenna headers", () => {
    const result = parseAssignmentPages([tablePage(1, [["Sector A", "700", "45", "2", "4"]],
      ["Sector", "Antenna", "Bearing degrees", "M-tilt degrees", "RET degrees"])]);
    expect(result.sectors[0]).toMatchObject({ azimuthDeg: 45, mechanicalTiltDeg: 2, electricalTiltDeg: 4 });
  });

  it("joins split label text and adjacent unit baseline without producing header sectors", () => {
    const page: PdfTextPage = { page: 1, items: [
      item("Sector", 20, 700), item("Azimuth", 180, 700),
      item("Mechanical", 300, 700), item("tilt", 335, 700),
      item("Electrical", 420, 700), item("tilt", 460, 700),
      item("°", 180, 685), item("°", 300, 685), item("°", 420, 685),
      item("A", 30, 650), item("90", 190, 650), item("3", 310, 650), item("6", 430, 650),
    ] };
    const result = parseAssignmentPages([page]);
    expect(result.sectors).toHaveLength(1);
    expect(result.sectors[0]).toMatchObject({ azimuthDeg: 90, mechanicalTiltDeg: 3, electricalTiltDeg: 6, warnings: [] });
  });

  it("preserves missing values as null rather than default zero", () => {
    const result = parseAssignmentPages([tablePage(1, [["A", "700", "—", "", "4"], ["B", "1800", "0", "0", ""]])]);
    expect(result.sectors[0]).toMatchObject({ azimuthDeg: null, mechanicalTiltDeg: null, electricalTiltDeg: 4 });
    expect(result.sectors[0].warnings.join(" ")).toMatch(/Azimut/);
    expect(result.sectors[1]).toMatchObject({ azimuthDeg: 0, mechanicalTiltDeg: 0, electricalTiltDeg: null });
  });

  it("keeps explicit mechanical/electrical values while warning about an ambiguous generic tilt", () => {
    const result = parseAssignmentPages([tablePage(1, [["A", "700", "120", "2", "4", "9"]],
      ["Sector", "Band", "Azimuth °", "Mechanical tilt °", "Electrical tilt °", "Tilt °"])]);
    expect(result.sectors[0]).toMatchObject({ mechanicalTiltDeg: 2, electricalTiltDeg: 4 });
    expect(result.sectors[0].sourceText).toContain("9");
    expect(result.sectors[0].warnings.join(" ")).toMatch(/nelze bezpečně přiřadit/);
  });

  it("never guesses the type of a generic tilt-only column", () => {
    const page: PdfTextPage = { page: 1, items: [
      item("Sektor", 20, 700), item("Azimut °", 180, 700), item("Tilt °", 300, 700),
      item("A", 30, 650), item("45", 190, 650), item("7", 310, 650),
    ] };
    const sector = parseAssignmentPages([page]).sectors[0];
    expect(sector).toMatchObject({ azimuthDeg: 45, mechanicalTiltDeg: null, electricalTiltDeg: null });
    expect(sector.warnings.join(" ")).toMatch(/Tilt/);
  });

  it("handles repeated page headers and preserves separate antennas in the same sector", () => {
    const result = parseAssignmentPages([
      tablePage(1, [["A", "700", "120", "2", "4"]]),
      tablePage(2, [["A", "1800", "120", "2", "6"], ["A", "1800", "125", "2", "7"]]),
    ]);
    expect(result.sectors).toHaveLength(3);
    expect(new Set(result.sectors.map(sector => sector.id)).size).toBe(3);
    expect(result.sectors.map(sector => sector.name)).toEqual(["A / 700", "A / 1800", "A / 1800"]);
    expect(result.sectors[2].warnings.join(" ")).toMatch(/Opakované/);
    expect(result.sectors[1].electricalTiltDeg).toBe(6);
  });

  it("rejects invalid ranges, conflicts and foreign units without extracting a plausible substring", () => {
    const result = parseAssignmentPages([tablePage(1, [
      ["A", "700", "361", "100", "unknown"],
      ["B", "700", "45 / 50", "2 rad", "3%"],
    ])]);
    for (const sector of result.sectors) {
      expect(sector.azimuthDeg).toBeNull();
      expect(sector.mechanicalTiltDeg).toBeNull();
      expect(sector.electricalTiltDeg).toBeNull();
      expect(sector.warnings.length).toBeGreaterThan(0);
    }
    expect(result.sectors[1].sourceText).toContain("45 / 50");
  });

  it("sets a conflicting duplicate azimuth column to null rather than picking a value", () => {
    const page: PdfTextPage = { page: 1, items: [
      item("Sector", 20, 700), item("Azimuth °", 180, 700), item("Azimut °", 300, 700),
      item("A", 30, 650), item("45", 190, 650), item("50", 310, 650),
    ] };
    const sector = parseAssignmentPages([page]).sectors[0];
    expect(sector.azimuthDeg).toBeNull();
    expect(sector.warnings.join(" ")).toMatch(/rozdílné hodnoty/);
  });

  it("retains an unambiguous azimuth without stated units, but requires review of assumed degrees", () => {
    const result = parseAssignmentPages([tablePage(1, [["A", "700", "45", "2", "4"]],
      ["Sector", "Band", "Azimuth", "Mechanical tilt", "Electrical tilt"])]);
    expect(result.sectors[0]).toMatchObject({ azimuthDeg: 45, mechanicalTiltDeg: 2, electricalTiltDeg: 4 });
    expect(result.sectors[0].warnings.join(" ")).toMatch(/předpoklad stupňů/);
  });

  it("uses explicit degree context instead of warning for every header", () => {
    const page = tablePage(1, [["A", "700", "45", "2", "4"]],
      ["Sector", "Band", "Azimuth", "MTilt", "ETilt"]);
    page.items.push(item("All angles are in degrees", 20, 740));
    expect(parseAssignmentPages([page]).sectors[0].warnings).toEqual([]);
  });

  it("does not claim OCR or transpose recognition", () => {
    expect(parseAssignmentPages([{ page: 1, items: [] }]).sectors).toEqual([]);
    const result = parseAssignmentPages([{ page: 1, items: [
      item("Sector A B C", 20, 700), item("Azimuth 120 240 0", 20, 680),
      item("Mechanical tilt 2 3 4", 20, 660),
    ] }]);
    expect(result.sectors).toEqual([]);
    expect(result.warnings.join(" ")).toMatch(/OCR/);
  });

  it("reads only explicitly labeled WGS84 coordinates and preserves conflicting metadata as unknown", () => {
    const page = tablePage(1, [["A", "700", "45", "2", "4"]]);
    page.items.push(item("Site code: A4TRI", 20, 780), item("Site name: Test locality", 20, 765),
      item("WGS84 Latitude: 50,12 Longitude: 14,34", 20, 750));
    const result = parseAssignmentPages([page]);
    expect(result).toMatchObject({ siteCode: "A4TRI", name: "Test locality", latitude: 50.12, longitude: 14.34 });
    const conflict = { page: 2, items: [item("Site code: OTHER", 20, 780), item("WGS84 Latitude: 50.13", 20, 750)] };
    const conflicted = parseAssignmentPages([page, conflict]);
    expect(conflicted.siteCode).toBe("");
    expect(conflicted.latitude).toBeNull();
    expect(conflicted.warnings.join(" ")).toMatch(/rozdílné/);
    const unlabeledCrs = parseAssignmentPages([{ page: 1, items: [item("Latitude: 50.12 Longitude: 14.34", 20, 750)] }]);
    expect(unlabeledCrs.latitude).toBeNull();
    expect(unlabeledCrs.longitude).toBeNull();
  });

  it("caps rows at 300 and pages at 50, with visible truncation warnings", () => {
    const rows = Array.from({ length: 301 }, (_, index) => ["S" + index, "700", "45", "2", "4"]);
    const result = parseAssignmentPages([tablePage(1, rows)]);
    expect(result.sectors).toHaveLength(300);
    expect(result.warnings.join(" ")).toMatch(/300/);
    const pages = Array.from({ length: 51 }, (_, index) => ({ page: index + 1, items: [] }));
    expect(parseAssignmentPages(pages).warnings.join(" ")).toMatch(/50/);
  });
});
