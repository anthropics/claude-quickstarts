import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { AUTH, createSessionToken, sessionCookieOptions, verifyPassword } from "@/lib/auth";

const MAX_ATTEMPTS = 5;
const WINDOW_MINUTES = 15;

export async function POST(req: NextRequest) {
  const { email, password } = await req.json().catch(() => ({}));
  if (!email || !password) {
    return NextResponse.json({ error: "Email and password are required" }, { status: 400 });
  }

  const db = getDb();
  const normalized = String(email).trim().toLowerCase();
  const ip = req.headers.get("x-forwarded-for") ?? "local";

  const recentFailures = (db.prepare(
    `SELECT COUNT(*) AS n FROM login_attempts
     WHERE email = ? AND success = 0 AND attempted_at > datetime('now', ?)`
  ).get(normalized, `-${WINDOW_MINUTES} minutes`) as { n: number }).n;
  if (recentFailures >= MAX_ATTEMPTS) {
    return NextResponse.json(
      { error: `Too many failed attempts. Try again in ${WINDOW_MINUTES} minutes.` },
      { status: 429 }
    );
  }

  const user = db.prepare(
    "SELECT id, work_email, password_hash, token_version, status FROM employees WHERE lower(work_email) = ?"
  ).get(normalized) as { id: number; work_email: string; password_hash: string | null; token_version: number; status: string } | undefined;

  const valid = user?.password_hash && user.status !== "terminated"
    ? await verifyPassword(String(password), user.password_hash)
    : false;

  db.prepare("INSERT INTO login_attempts (email, ip, success) VALUES (?, ?, ?)").run(normalized, ip, valid ? 1 : 0);

  if (!valid || !user) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  db.prepare("UPDATE employees SET last_login_at = datetime('now') WHERE id = ?").run(user.id);
  logAudit(user.id, "auth.login", "employee", user.id);

  const token = await createSessionToken({ sub: user.id, tv: user.token_version });
  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH.cookieName, token, sessionCookieOptions());
  return res;
}
