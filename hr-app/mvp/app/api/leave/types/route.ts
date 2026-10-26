import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function POST(request: Request) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Only HR/admin can manage leave types." }, { status: 403 });
  }

  let body: {
    name?: string;
    code?: string;
    colour?: string;
    annual_entitlement_days?: number;
    paid?: boolean;
    probation_restricted?: boolean;
    negative_balance_allowed?: boolean;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const name = typeof body.name === "string" ? body.name.trim() : "";
  const code = typeof body.code === "string" ? body.code.trim().toUpperCase() : "";
  if (!name || !code) {
    return NextResponse.json({ error: "Name and code are required." }, { status: 400 });
  }
  if (!/^[A-Z0-9_]+$/.test(code)) {
    return NextResponse.json({ error: "Code may only contain letters, numbers and underscores." }, { status: 400 });
  }
  const entitlement = Number(body.annual_entitlement_days ?? 0);
  if (!Number.isFinite(entitlement) || entitlement < 0) {
    return NextResponse.json({ error: "Entitlement must be a non-negative number of days." }, { status: 400 });
  }
  const colour =
    typeof body.colour === "string" && /^#[0-9a-fA-F]{6}$/.test(body.colour) ? body.colour : "#3b5bdb";

  const db = getDb();
  const exists = db.prepare("SELECT id FROM leave_types WHERE code = ?").get(code);
  if (exists) {
    return NextResponse.json({ error: `A leave type with code '${code}' already exists.` }, { status: 400 });
  }

  const result = db
    .prepare(
      `INSERT INTO leave_types (name, code, colour, annual_entitlement_days, paid, probation_restricted, negative_balance_allowed)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    )
    .run(name, code, colour, entitlement, body.paid ? 1 : 0, body.probation_restricted ? 1 : 0, body.negative_balance_allowed ? 1 : 0);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "leave_type", id, `${code} (${entitlement}d)`);

  return NextResponse.json({ id }, { status: 201 });
}
