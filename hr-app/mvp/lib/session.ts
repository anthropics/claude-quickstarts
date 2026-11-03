import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { getDb } from "./db";
import { AUTH, verifySessionToken } from "./auth";
import type { Employee } from "./types";

export interface CurrentUser extends Employee {
  /** Set when an admin is impersonating this user (holds the admin's id). */
  impersonated_by: number | null;
}

/**
 * Resolves the authenticated user from the session cookie. Returns null when
 * unauthenticated or the session was revoked (token_version bumped).
 * Cached per-request so layouts + pages share one lookup.
 */
export const getSessionUser = cache((): CurrentUser | null => {
  const token = cookies().get(AUTH.cookieName)?.value;
  if (!token) return null;
  // verifySessionToken is async (jose), but session resolution is needed in
  // sync server components; verification also happens in middleware for every
  // request, so here we decode through a sync bridge.
  const payload = decodeVerifiedSync(token);
  if (!payload) return null;

  const db = getDb();
  const account = db.prepare("SELECT * FROM employees WHERE id = ? AND status != 'terminated'").get(payload.sub) as
    | (Employee & { token_version: number })
    | undefined;
  if (!account || account.token_version !== payload.tv) return null;

  if (payload.imp && account.role === "admin") {
    const target = db.prepare("SELECT * FROM employees WHERE id = ? AND status != 'terminated'").get(payload.imp) as Employee | undefined;
    if (target) return { ...target, impersonated_by: account.id };
  }
  return { ...account, impersonated_by: null };
});

// jose is async-only; middleware has already verified the signature for every
// app route, so inside the request we re-verify synchronously via Atomics.wait
// on a worker... — in practice the simplest correct sync bridge for Node is
// deasync-style busy waiting, which we avoid: instead we verify HMAC directly
// with node:crypto (same HS256 semantics as jose).
import { createHmac, timingSafeEqual } from "crypto";

function decodeVerifiedSync(token: string): { sub: number; tv: number; imp?: number } | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [h, p, sig] = parts;
  const secret = process.env.SESSION_SECRET ?? "hrcore-dev-only-secret-do-not-use-in-production";
  const expected = createHmac("sha256", secret).update(`${h}.${p}`).digest("base64url");
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    const payload = JSON.parse(Buffer.from(p, "base64url").toString());
    if (payload.exp && payload.exp * 1000 < Date.now()) return null;
    if (!payload.sub) return null;
    return { sub: Number(payload.sub), tv: Number(payload.tv ?? 0), imp: payload.imp ? Number(payload.imp) : undefined };
  } catch {
    return null;
  }
}

/** For pages: returns the user or redirects to /login. */
export function getCurrentUser(): CurrentUser {
  const user = getSessionUser();
  if (!user) redirect("/login");
  return user;
}

/** For API routes: returns the user or null (caller returns 401). */
export function getApiUser(): CurrentUser | null {
  return getSessionUser();
}

export function canManage(user: Employee): boolean {
  return user.role === "admin" || user.role === "hr" || user.role === "manager";
}

export function isHr(user: Employee): boolean {
  return user.role === "admin" || user.role === "hr";
}
