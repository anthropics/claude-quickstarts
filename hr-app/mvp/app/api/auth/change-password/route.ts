import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { AUTH, createSessionToken, hashPasswordSync, sessionCookieOptions, verifyPassword } from "@/lib/auth";
import { getApiUser } from "@/lib/session";

export async function POST(req: NextRequest) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (user.impersonated_by) {
    return NextResponse.json({ error: "Cannot change a password while impersonating" }, { status: 403 });
  }

  const { current_password, new_password } = await req.json().catch(() => ({}));
  if (!current_password || !new_password) {
    return NextResponse.json({ error: "Current and new password are required" }, { status: 400 });
  }
  if (String(new_password).length < 10) {
    return NextResponse.json({ error: "New password must be at least 10 characters" }, { status: 400 });
  }

  const db = getDb();
  const row = db.prepare("SELECT password_hash, token_version FROM employees WHERE id = ?").get(user.id) as
    | { password_hash: string; token_version: number }
    | undefined;
  if (!row || !(await verifyPassword(String(current_password), row.password_hash))) {
    return NextResponse.json({ error: "Current password is incorrect" }, { status: 403 });
  }

  // Bump token_version to revoke every other session, then re-issue this one.
  const newVersion = row.token_version + 1;
  db.prepare(
    "UPDATE employees SET password_hash = ?, must_change_password = 0, token_version = ? WHERE id = ?"
  ).run(hashPasswordSync(String(new_password)), newVersion, user.id);
  logAudit(user.id, "auth.change_password", "employee", user.id);

  const token = await createSessionToken({ sub: user.id, tv: newVersion });
  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH.cookieName, token, sessionCookieOptions());
  return res;
}
