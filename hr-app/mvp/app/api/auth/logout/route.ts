import { NextResponse } from "next/server";
import { AUTH } from "@/lib/auth";
import { getApiUser } from "@/lib/session";
import { logAudit } from "@/lib/db";

export async function POST() {
  const user = getApiUser();
  if (user) logAudit(user.impersonated_by ?? user.id, "auth.logout", "employee", user.id);
  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH.cookieName, "", { path: "/", maxAge: 0 });
  return res;
}
