import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { AUTH, createSessionToken, sessionCookieOptions } from "@/lib/auth";
import { getApiUser } from "@/lib/session";

/** Admin-only impersonation. POST {employee_id} to start, POST {stop:true} to end. Fully audited. */
export async function POST(req: NextRequest) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const db = getDb();
  const body = await req.json().catch(() => ({}));

  // The real account is the impersonator when already impersonating.
  const realId = user.impersonated_by ?? user.id;
  const real = db.prepare("SELECT id, role, token_version FROM employees WHERE id = ?").get(realId) as
    | { id: number; role: string; token_version: number }
    | undefined;
  if (!real || real.role !== "admin") {
    return NextResponse.json({ error: "Only admins can impersonate" }, { status: 403 });
  }

  if (body.stop) {
    logAudit(real.id, "auth.impersonate_stop", "employee", user.id);
    const token = await createSessionToken({ sub: real.id, tv: real.token_version });
    const res = NextResponse.json({ ok: true });
    res.cookies.set(AUTH.cookieName, token, sessionCookieOptions());
    return res;
  }

  const targetId = Number(body.employee_id);
  const target = db.prepare("SELECT id FROM employees WHERE id = ? AND status != 'terminated'").get(targetId);
  if (!target) return NextResponse.json({ error: "Employee not found" }, { status: 404 });
  if (targetId === real.id) return NextResponse.json({ error: "Cannot impersonate yourself" }, { status: 400 });

  logAudit(real.id, "auth.impersonate_start", "employee", targetId);
  const token = await createSessionToken({ sub: real.id, tv: real.token_version, imp: targetId });
  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH.cookieName, token, sessionCookieOptions());
  return res;
}
