import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { getAerialTileset as GetAerialTileset, resolveTileUrl as ResolveTileUrl } from "./mapycz";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => body,
  } as Response;
}

function cuzkMetadata() {
  return {
    minLOD: 0,
    maxLOD: 19,
    tileInfo: {
      rows: 256,
      cols: 256,
      spatialReference: { wkid: 102100, latestWkid: 3857 },
      // The service advertises a full tile-grid definition, while available
      // imagery is restricted by maxLOD. Do not overzoom to this final level.
      lods: [{ level: 0 }, { level: 19 }, { level: 23 }],
    },
  };
}

describe("getAerialTileset", () => {
  const originalKey = process.env.MAPY_CZ_API_KEY;
  let getAerialTileset: typeof GetAerialTileset;

  // The module caches its resolved tileset at module scope, so each test
  // needs a fresh module instance (vi.resetModules() only takes effect on
  // the next import, not on bindings already resolved by a static import).
  beforeEach(async () => {
    process.env.MAPY_CZ_API_KEY = "test-key";
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn());
    ({ getAerialTileset } = await import("./mapycz"));
  });

  afterEach(() => {
    if (originalKey === undefined) delete process.env.MAPY_CZ_API_KEY;
    else process.env.MAPY_CZ_API_KEY = originalKey;
    vi.unstubAllGlobals();
  });

  it("extracts tileUrlTemplate/minZoom/maxZoom/attribution from a well-formed TileJSON response", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        tiles: ["https://api.mapy.cz/v1/maptiles/aerial/256@1x/{z}/{x}/{y}?apikey=test-key"],
        minzoom: 0,
        maxzoom: 20,
        attribution: "© Seznam.cz a.s. a další",
      })
    );

    const tileset = await getAerialTileset();

    expect(tileset.tileUrlTemplate).toBe(
      "https://api.mapy.cz/v1/maptiles/aerial/256@1x/{z}/{x}/{y}?apikey=test-key"
    );
    expect(tileset.minZoom).toBe(0);
    expect(tileset.maxZoom).toBe(20);
    expect(tileset.attribution).toBe("© Seznam.cz a.s. a další");
  });

  it("falls back to sane defaults when minzoom/maxzoom/attribution are missing", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        tiles: ["https://api.mapy.cz/v1/maptiles/aerial/256@1x/{z}/{x}/{y}?apikey=test-key"],
      })
    );

    const tileset = await getAerialTileset();

    expect(tileset.maxZoom).toBe(19);
    expect(tileset.minZoom).toBe(0);
    expect(tileset.attribution.length).toBeGreaterThan(0);
  });

  it("throws when the response has no usable tiles[] template", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ minzoom: 0, maxzoom: 19 }));

    await expect(getAerialTileset()).rejects.toThrow(/tiles\[\]/);
  });

  it("throws when the fetch itself fails, and does not cache the failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}, false, 502));

    await expect(getAerialTileset()).rejects.toThrow(/502/);

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        tiles: ["https://api.mapy.cz/v1/maptiles/aerial/256@1x/{z}/{x}/{y}?apikey=test-key"],
        maxzoom: 19,
      })
    );
    await expect(getAerialTileset()).resolves.toMatchObject({ maxZoom: 19 });
  });

  it("uses public ČÚZK orthophoto without a key and respects available maxLOD rather than the highest grid LOD", async () => {
    delete process.env.MAPY_CZ_API_KEY;
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(cuzkMetadata()));

    const tileset = await getAerialTileset();

    expect(fetch).toHaveBeenCalledWith(
      "https://ags.cuzk.gov.cz/arcgis1/rest/services/ORTOFOTO_WM/MapServer?f=pjson",
      expect.objectContaining({ signal: expect.anything() })
    );
    expect(tileset).toMatchObject({
      name: "Ortofoto ČÚZK · Česko",
      minZoom: 0,
      maxZoom: 19,
      tileUrlTemplate: "https://ags.cuzk.gov.cz/arcgis1/rest/services/ORTOFOTO_WM/MapServer/tile/{z}/{y}/{x}",
    });
    expect(tileset.attribution).toContain("ČÚZK");
    expect(tileset.attribution).toContain("https://geoportal.cuzk.gov.cz/");
  });

  it("caches a successful no-key resolution without fetching the metadata again", async () => {
    delete process.env.MAPY_CZ_API_KEY;
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(cuzkMetadata()));

    const first = await getAerialTileset();
    const second = await getAerialTileset();

    expect(second).toBe(first);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["missing tile info", { tileInfo: undefined }],
    ["unsupported coordinate system", { tileInfo: { ...cuzkMetadata().tileInfo, spatialReference: { wkid: 4326 } } }],
    ["wrong tile height", { tileInfo: { ...cuzkMetadata().tileInfo, rows: 512 } }],
    ["wrong tile width", { tileInfo: { ...cuzkMetadata().tileInfo, cols: 512 } }],
    ["missing minimum LOD", { minLOD: undefined }],
    ["fractional maximum LOD", { maxLOD: 19.5 }],
    ["negative minimum LOD", { minLOD: -1 }],
    ["maximum before minimum", { minLOD: 20, maxLOD: 19 }],
    ["out-of-range maximum LOD", { maxLOD: 23 }],
  ] as const)("rejects ČÚZK metadata with %s", async (_reason, invalid) => {
    delete process.env.MAPY_CZ_API_KEY;
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ ...cuzkMetadata(), ...invalid }));

    await expect(getAerialTileset()).rejects.toThrow("Unsupported ČÚZK tile grid");
  });

  it.each(["unavailable", "invalid"])("retries no-key metadata after an %s response", async (failure) => {
    delete process.env.MAPY_CZ_API_KEY;
    vi.mocked(fetch)
      .mockResolvedValueOnce(failure === "unavailable"
        ? jsonResponse({}, false, 502)
        : jsonResponse({ ...cuzkMetadata(), maxLOD: 23 }))
      .mockResolvedValueOnce(jsonResponse(cuzkMetadata()));

    await expect(getAerialTileset()).rejects.toThrow();
    await expect(getAerialTileset()).resolves.toMatchObject({ maxZoom: 19, name: "Ortofoto ČÚZK · Česko" });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("preserves the configured Mapy.com provider path and encodes its API key", async () => {
    process.env.MAPY_CZ_API_KEY = "a+b?key";
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({
      tiles: ["https://api.mapy.com/aerial/{z}/{x}/{y}?apikey=a%2Bb%3Fkey"],
      minzoom: 1,
      maxzoom: 20,
      attribution: "Mapy attribution",
    }));

    await expect(getAerialTileset()).resolves.toMatchObject({
      name: "Letecká mapa Mapy.com", minZoom: 1, maxZoom: 20,
      tileUrlTemplate: "https://api.mapy.com/aerial/{z}/{x}/{y}?apikey=a%2Bb%3Fkey",
    });
    expect(fetch).toHaveBeenCalledWith(
      "https://api.mapy.com/v1/maptiles/aerial/tiles.json?apikey=a%2Bb%3Fkey",
      expect.objectContaining({ signal: expect.anything() })
    );
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

describe("resolveTileUrl", () => {
  let resolveTileUrl: typeof ResolveTileUrl;

  beforeEach(async () => {
    ({ resolveTileUrl } = await import("./mapycz"));
  });

  it("substitutes z/x/y into the template", () => {
    expect(resolveTileUrl("https://example.com/{z}/{x}/{y}?apikey=k", 12, 3, 4)).toBe(
      "https://example.com/12/3/4?apikey=k"
    );
  });

  it("keeps ČÚZK row-before-column z/y/x ordering", () => {
    expect(resolveTileUrl("https://example.com/tile/{z}/{y}/{x}", 19, 281, 172)).toBe(
      "https://example.com/tile/19/172/281"
    );
  });
});
