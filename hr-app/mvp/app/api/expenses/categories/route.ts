import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function POST(request: Request) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Only HR can manage expense categories." }, { status: 403 });
  }
  const db = getDb();

  let body: { name?: string; code?: string; monthly_limit?: number | null; requires_receipt?: boolean };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) {
    return NextResponse.json({ error: "Name is required." }, { status: 400 });
  }

  const code = typeof body.code === "string" ? body.code.trim().toUpperCase() : "";
  if (!code || !/^[A-Z0-9_]+$/.test(code)) {
    return NextResponse.json({ error: "Code is required (letters, digits and underscores only)." }, { status: 400 });
  }

  let monthlyLimit: number | null = null;
  if (body.monthly_limit !== undefined && body.monthly_limit !== null) {
    if (typeof body.monthly_limit !== "number" || !Number.isFinite(body.monthly_limit) || body.monthly_limit <= 0) {
      return NextResponse.json({ error: "Monthly limit must be a positive amount (or blank for no limit)." }, { status: 400 });
    }
    monthlyLimit = body.monthly_limit;
  }

  const requiresReceipt = body.requires_receipt === false ? 0 : 1;

  const existing = db.prepare("SELECT id FROM expense_categories WHERE code = ?").get(code) as
    | { id: number }
    | undefined;
  if (existing) {
    return NextResponse.json({ error: `A category with code ${code} already exists.` }, { status: 400 });
  }

  const result = db
    .prepare("INSERT INTO expense_categories (name, code, monthly_limit, requires_receipt) VALUES (?, ?, ?, ?)")
    .run(name, code, monthlyLimit, requiresReceipt);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "expense_category", id, code);

  return NextResponse.json({ id, name, code }, { status: 201 });
}
