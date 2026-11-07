import { afterEach, describe, expect, it, vi } from "vitest";
vi.mock("@/lib/mapycz", () => ({ getAerialTileset: vi.fn() }));
import { getAerialTileset } from "@/lib/mapycz";
import { GET, runtime } from "../app/api/basemap-meta/route";
afterEach(() => vi.restoreAllMocks());
describe("basemap metadata endpoint", () => {
  it("uses the same edge runtime as the tile proxy", () => { expect(runtime).toBe("edge"); });
  it("returns provider metadata without a server-only tile URL", async () => {
    vi.mocked(getAerialTileset).mockResolvedValue({name:"Ortofoto ČÚZK · Česko",attribution:"ČÚZK",minZoom:6,maxZoom:20,tileUrlTemplate:"https://private.test/{z}/{x}/{y}?apikey=never-public"});
    const response=await GET();
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({name:"Ortofoto ČÚZK · Česko",attribution:"ČÚZK",minZoom:6,maxZoom:20});
  });
  it("keeps upstream exception messages and URLs out of logs and response", async () => {
    const warning=vi.spyOn(console,"warn").mockImplementation(()=>{});
    vi.mocked(getAerialTileset).mockRejectedValue(new Error("private.test?apikey=never-public",{cause:{code:"ECONNRESET"}}));
    const response=await GET();
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({error:"Basemap tileset unavailable"});
    expect(warning).toHaveBeenCalledWith("[basemap-meta] resolver failed",{errorType:"Error",code:"ECONNRESET"});
    expect(JSON.stringify(warning.mock.calls)).not.toContain("never-public");
  });
});
