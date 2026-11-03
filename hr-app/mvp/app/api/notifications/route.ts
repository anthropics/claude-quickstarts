import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { getApiUser } from "@/lib/session";

export async function GET() {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const rows = getDb()
    .prepare("SELECT * FROM notifications WHERE employee_id = ? ORDER BY created_at DESC LIMIT 30")
    .all(user.id);
  return NextResponse.json({ notifications: rows });
}

/** PATCH marks all (or one via {id}) as read. */
export async function PATCH(req: NextRequest) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  const db = getDb();
  if (body.id) {
    db.prepare("UPDATE notifications SET read_at = datetime('now') WHERE id = ? AND employee_id = ?").run(Number(body.id), user.id);
  } else {
    db.prepare("UPDATE notifications SET read_at = datetime('now') WHERE employee_id = ? AND read_at IS NULL").run(user.id);
  }
  return NextResponse.json({ ok: true });
}
