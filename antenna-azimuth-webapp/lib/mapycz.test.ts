import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { getAerialTileset as GetAerialTileset, resolveTileUrl as ResolveTileUrl } from "./mapycz";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => body,
  } as Response;
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
    process.env.MAPY_CZ_API_KEY = originalKey;
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
});
