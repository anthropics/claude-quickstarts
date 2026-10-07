import type { ProjectSector } from "./projects";

export type PdfTextItem = { text: string; x: number; y: number };
/** PDF.js coordinates: x rightwards and y upwards. No OCR. */
export type PdfTextPage = { page: number; items: PdfTextItem[] };
type Kind = "sector" | "identity" | "azimuth" | "mechanical" | "electrical" | "generic";
type Line = { y: number; items: PdfTextItem[] };
type Column = { kind: Kind; x: number; label: string; degrees: boolean };
const normalized = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const hasDegrees = (text: string) => /°|\bdeg(?:rees?)?\b|stup[nň]/i.test(text);
const lineText = (line: Line) => line.items.map(item => item.text.trim()).join(" ").trim();

function kindOf(text: string): Kind | null {
  const value = normalized(text).replace(/[–−]/g, "-");
  if (/\b(sektor|sector)\b/.test(value)) return "sector";
  if (/\b(azimut|azimuth|bearing)\b/.test(value)) return "azimuth";
  if (/mechanic|mechanick|\bm\s*-?\s*tilt\b/.test(value)) return "mechanical";
  if (/electric|elektrick|\be\s*-?\s*tilt\b|\bret\b/.test(value)) return "electrical";
  if (/\b(antena|antenna|band|pasmo)\b/.test(value)) return "identity";
  if (/\btilt\b|sklon/.test(value)) return "generic";
  return null;
}

function linesOf(items: PdfTextItem[]): Line[] {
  const sorted = items.filter(item => item.text.trim() && Number.isFinite(item.x) && Number.isFinite(item.y))
    .slice(0, 20000).sort((a, b) => b.y - a.y || a.x - b.x);
  const lines: Line[] = [];
  for (const item of sorted) {
    const last = lines[lines.length - 1];
    if (last && Math.abs(last.y - item.y) <= 3) last.items.push(item);
    else lines.push({ y: item.y, items: [item] });
  }
  for (const line of lines) line.items.sort((a, b) => a.x - b.x);
  return lines;
}

function numeric(text: string): number | null {
  // Only a complete numeric cell; conflicting values and different units are not guessed.
  const match = text.trim().replace(/[−–]/g, "-").match(/^([+-]?\d+(?:[.,]\d+)?)\s*(?:°|deg(?:rees?)?|stup[nň](?:e|u|ů)?)?$/i);
  if (!match) return null;
  const value = Number(match[1].replace(",", "."));
  return Number.isFinite(value) ? value : null;
}

function header(line: Line): Column[] | null {
  const columns: Column[] = [];
  for (const item of line.items) {
    const kind = kindOf(item.text);
    const previous = columns[columns.length - 1];
    // Extraction can split "Mechanical tilt (°)" across text items.
    if (kind === "generic" && previous && ["mechanical", "electrical"].includes(previous.kind) && item.x - previous.x <= 85) {
      previous.label += " " + item.text;
      previous.degrees ||= hasDegrees(item.text);
    } else if (kind) columns.push({ kind, x: item.x, label: item.text, degrees: hasDegrees(item.text) });
    else if (previous && item.x - previous.x <= 85) {
      previous.label += " " + item.text;
      previous.degrees ||= hasDegrees(item.text);
    }
  }
  const kinds = columns.map(column => column.kind);
  return kinds.includes("sector") && kinds.some(kind => ["azimuth", "mechanical", "electrical", "generic"].includes(kind))
    ? columns : null;
}

function cellTexts(line: Line, columns: Column[]): string[] {
  return columns.map((column, index) => {
    const left = index === 0 ? -Infinity : (columns[index - 1].x + column.x) / 2;
    const right = index === columns.length - 1 ? Infinity : (column.x + columns[index + 1].x) / 2;
    return line.items.filter(item => item.x >= left && item.x < right).map(item => item.text).join(" ").trim();
  });
}

export function parseAssignmentPages(pages: PdfTextPage[]): {
  sectors: ProjectSector[]; warnings: string[]; siteCode: string; name: string;
  latitude: number | null; longitude: number | null;
} {
  const sectors: ProjectSector[] = [], warnings: string[] = [];
  const siteCodes: string[] = [], names: string[] = [], latitudes: number[] = [], longitudes: number[] = [];
  const seen = new Set<string>();
  let capped = false;
  if (pages.length > 50) warnings.push("Zpracováno pouze prvních 50 stran. Zbytek zkontrolujte ručně.");
  for (const page of pages.slice(0, 50)) {
    if (page.items.length > 20000) warnings.push("Strana " + page.page + ": limit 20 000 textových položek.");
    const lines = linesOf(page.items);
    const wgs84 = lines.some(line => /wgs\s*84|epsg\s*:?\s*4326/i.test(lineText(line)));
    for (const line of lines) {
      const text = lineText(line), value = normalized(text);
      const site = text.match(/(?:kód\s+lokality|kod\s+lokality|site\s+code|site\s+id|lokalita)\s*[:=]\s*([a-z0-9_-]{2,24})\b/i);
      const name = text.match(/(?:název\s+lokality|nazev\s+lokality|site\s+name)\s*[:=]\s*(.+)$/i);
      if (site) siteCodes.push(site[1]);
      if (name) names.push(name[1].trim());
      if (wgs84) {
        const lat = value.match(/(?:latitude|zemepisna\s+sirka)\s*[:=]\s*([+-]?\d+(?:[.,]\d+)?)/);
        const lon = value.match(/(?:longitude|zemepisna\s+delka)\s*[:=]\s*([+-]?\d+(?:[.,]\d+)?)/);
        if (lat) latitudes.push(Number(lat[1].replace(",", ".")));
        if (lon) longitudes.push(Number(lon[1].replace(",", ".")));
      }
    }
    let columns: Column[] | null = null, headerY = 0;
    const contextDegrees = lines.some(line => /(?:uhly|angles).*?(?:stup|degrees)|(?:stup|degrees).*?(?:uhly|angles)/i.test(normalized(lineText(line))));
    for (const line of lines) {
      const found = header(line);
      if (found) { columns = found; headerY = line.y; continue; }
      if (!columns) continue;
      const values = cellTexts(line, columns);
      // Attach one nearby second header baseline, never numerical data.
      if (headerY - line.y <= 24 && line.items.every(item => numeric(item.text) == null) &&
          values.some(value => hasDegrees(value) || /tilt|sklon/i.test(value))) {
        columns.forEach((column, index) => { column.label += " " + values[index]; column.degrees ||= hasDegrees(values[index]); });
        continue;
      }
      const sectorIndex = columns.findIndex(column => column.kind === "sector");
      const sectorName = values[sectorIndex]?.trim() ?? "";
      const cells = columns.map((column, index) => ({ column, raw: values[index] }))
        .filter(cell => ["azimuth", "mechanical", "electrical", "generic"].includes(cell.column.kind));
      if (!cells.some(cell => /\d|^[-–—]$/.test(cell.raw)) || /^(page|strana)\b/i.test(sectorName)) continue;
      if (sectors.length === 300) { capped = true; break; }
      const identity = columns.map((column, index) => column.kind === "identity" ? values[index] : "").filter(Boolean).join(" / ");
      const rowName = [sectorName, identity].filter(Boolean).join(" / ") || "Neoznačený řádek " + (sectors.length + 1);
      const rowWarnings: string[] = [];
      if (!sectorName) rowWarnings.push("Chybí označení sektoru; potvrďte řádek ručně.");
      const read = (kind: Kind, title: string): number | null => {
        const candidates: number[] = [];
        let invalid = false;
        for (const cell of cells.filter(cell => cell.column.kind === kind)) {
          if (!cell.raw || /^[-–—]$|^(?:n\/?a|null)$/i.test(cell.raw)) continue;
          const value = numeric(cell.raw);
          if (value == null || (kind === "azimuth" && (value < 0 || value > 360)) ||
              (kind !== "azimuth" && Math.abs(value) > 90)) {
            rowWarnings.push(title + ": nejednoznačná nebo neplatná hodnota „" + cell.raw + "“.");
            invalid = true;
            continue;
          }
          if (!cell.column.degrees && !contextDegrees && !hasDegrees(cell.raw))
            rowWarnings.push(title + ": jednotka není uvedena; potvrďte předpoklad stupňů podle zadání.");
          candidates.push(value);
        }
        if (new Set(candidates).size > 1) { rowWarnings.push(title + ": rozdílné hodnoty v jednom řádku."); return null; }
        return invalid ? null : candidates[0] ?? null;
      };
      const azimuthDeg = read("azimuth", "Azimut");
      const mechanicalTiltDeg = read("mechanical", "Mechanický tilt");
      const electricalTiltDeg = read("electrical", "Elektrický tilt");
      if (azimuthDeg == null) rowWarnings.push("Azimut chybí nebo vyžaduje ruční kontrolu.");
      if (cells.some(cell => cell.column.kind === "generic" && cell.raw.trim()))
        rowWarnings.push("Sloupec Tilt není mechanický ani elektrický; jeho hodnotu nelze bezpečně přiřadit.");
      if (seen.has(normalized(rowName))) rowWarnings.push("Opakované označení sektoru/antény; řádky nebyly sloučeny.");
      seen.add(normalized(rowName));
      sectors.push({ id: "pdf-p" + page.page + "-r" + (sectors.length + 1), name: rowName,
        azimuthDeg, mechanicalTiltDeg, electricalTiltDeg, sourcePage: page.page,
        sourceText: lineText(line), warnings: rowWarnings });
    }
    if (capped) break;
  }
  if (capped) warnings.push("Import omezen na 300 řádků. Zbytek zkontrolujte ručně.");
  if (!sectors.length) warnings.push("Nebyla nalezena jednoznačná řádková tabulka sektorů. Skeny a transponované tabulky vyžadují ruční zadání; OCR není použito.");
  const uniqueText = (values: string[], title: string): string => {
    const unique = [...new Set(values.map(value => value.trim()).filter(Boolean))];
    if (unique.length > 1) { warnings.push(title + ": rozdílné údaje; vyberte je ručně."); return ""; }
    return unique[0] ?? "";
  };
  const coordinate = (values: number[], limit: number, title: string): number | null => {
    const unique = [...new Set(values)];
    if (unique.length > 1 || unique.some(value => !Number.isFinite(value) || Math.abs(value) > limit)) {
      warnings.push(title + ": rozdílné nebo neplatné souřadnice; zadejte je ručně."); return null;
    }
    return unique[0] ?? null;
  };
  return { sectors, warnings, siteCode: uniqueText(siteCodes, "Kód lokality"), name: uniqueText(names, "Název lokality"),
    latitude: coordinate(latitudes, 90, "Zeměpisná šířka"), longitude: coordinate(longitudes, 180, "Zeměpisná délka") };
}
