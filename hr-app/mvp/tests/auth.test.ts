import { describe, it, expect } from "vitest";
import { hashPasswordSync, verifyPassword, createSessionToken, verifySessionToken } from "@/lib/auth";

describe("password hashing", () => {
  it("verifies a correct password", async () => {
    const hash = hashPasswordSync("Acme#2026");
    expect(await verifyPassword("Acme#2026", hash)).toBe(true);
  });

  it("rejects a wrong password", async () => {
    const hash = hashPasswordSync("Acme#2026");
    expect(await verifyPassword("wrong-password", hash)).toBe(false);
  });

  it("produces unique salts", () => {
    expect(hashPasswordSync("same")).not.toBe(hashPasswordSync("same"));
  });
});

describe("session tokens", () => {
  it("round-trips a session payload", async () => {
    const token = await createSessionToken({ sub: 42, tv: 3 });
    const payload = await verifySessionToken(token);
    expect(payload).toMatchObject({ sub: 42, tv: 3 });
    expect(payload?.imp).toBeUndefined();
  });

  it("carries impersonation", async () => {
    const token = await createSessionToken({ sub: 1, tv: 1, imp: 9 });
    const payload = await verifySessionToken(token);
    expect(payload?.imp).toBe(9);
  });

  it("rejects a tampered token", async () => {
    const token = await createSessionToken({ sub: 1, tv: 1 });
    const [h, p] = token.split(".");
    const forged = Buffer.from(JSON.stringify({ sub: "2", tv: 1, exp: 9999999999 })).toString("base64url");
    expect(await verifySessionToken(`${h}.${forged}.${token.split(".")[2]}`)).toBeNull();
    expect(await verifySessionToken(token + "x")).toBeNull();
    expect(await verifySessionToken(`${h}.${p}.`)).toBeNull();
  });
});
