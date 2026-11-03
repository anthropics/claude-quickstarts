import bcrypt from "bcryptjs";
import { SignJWT, jwtVerify } from "jose";

/**
 * Session/auth primitives. Sessions are stateless signed JWTs in an httpOnly
 * cookie; `token_version` on the employee row allows server-side revocation
 * (bump it to invalidate all existing sessions for that user).
 */

const SESSION_COOKIE = "hrcore_session";
const SESSION_TTL_HOURS = 8;

export const AUTH = {
  cookieName: SESSION_COOKIE,
  ttlSeconds: SESSION_TTL_HOURS * 3600,
};

function getSecret(): Uint8Array {
  const secret = process.env.SESSION_SECRET;
  if (!secret) {
    if (process.env.NODE_ENV === "production" && process.env.ALLOW_DEV_SECRET !== "1") {
      throw new Error("SESSION_SECRET must be set in production (see .env.example)");
    }
    return new TextEncoder().encode("hrcore-dev-only-secret-do-not-use-in-production");
  }
  return new TextEncoder().encode(secret);
}

export interface SessionPayload {
  sub: number;          // employee id
  tv: number;           // token_version at issue time
  imp?: number;         // impersonated employee id (admin feature)
}

export function hashPasswordSync(plain: string): string {
  return bcrypt.hashSync(plain, 10);
}

export async function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}

export async function createSessionToken(payload: SessionPayload): Promise<string> {
  return new SignJWT({ tv: payload.tv, ...(payload.imp ? { imp: payload.imp } : {}) })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(String(payload.sub))
    .setIssuedAt()
    .setExpirationTime(`${SESSION_TTL_HOURS}h`)
    .sign(getSecret());
}

export async function verifySessionToken(token: string): Promise<SessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, getSecret());
    if (!payload.sub) return null;
    return {
      sub: Number(payload.sub),
      tv: Number(payload.tv ?? 0),
      imp: payload.imp ? Number(payload.imp) : undefined,
    };
  } catch {
    return null;
  }
}

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: AUTH.ttlSeconds,
  };
}
