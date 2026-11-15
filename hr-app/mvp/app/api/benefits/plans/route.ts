import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import { isBenefitCategory } from "@/app/benefits/_lib/benefits";

export async function POST(request: Request) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Only HR and admins can create benefit plans." }, { status: 403 });
  }
  const db = getDb();

  let body: { name?: string; category?: string; provider?: string; description?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) {
    return NextResponse.json({ error: "Plan name is required." }, { status: 400 });
  }
  if (!isBenefitCategory(body.category)) {
    return NextResponse.json(
      { error: "Category must be one of: medical, retirement, life, disability, wellness." },
      { status: 400 }
    );
  }
  const provider = typeof body.provider === "string" && body.provider.trim() ? body.provider.trim() : null;
  const description =
    typeof body.description === "string" && body.description.trim() ? body.description.trim() : null;

  const result = db
    .prepare("INSERT INTO benefit_plans (name, category, provider, description, active) VALUES (?, ?, ?, ?, 1)")
    .run(name, body.category, provider, description);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "benefit_plan", id, `${name} (${body.category})`);

  return NextResponse.json({ id }, { status: 201 });
}
