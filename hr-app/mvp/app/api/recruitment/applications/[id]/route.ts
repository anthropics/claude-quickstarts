import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, canManage } from "@/lib/session";
import type { Application, ApplicationStage } from "@/lib/types";

const STAGE_ORDER: ApplicationStage[] = [
  "applied", "screening", "phone_screen", "interview", "assessment", "offer", "hired",
];

const VALID_NEXT: Record<ApplicationStage, ApplicationStage[]> = {
  applied: ["screening", "rejected", "withdrawn"],
  screening: ["phone_screen", "interview", "rejected", "withdrawn"],
  phone_screen: ["interview", "rejected", "withdrawn"],
  interview: ["assessment", "offer", "rejected", "withdrawn"],
  assessment: ["offer", "rejected", "withdrawn"],
  offer: ["hired", "rejected", "withdrawn"],
  hired: [],
  rejected: [],
  withdrawn: [],
};

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  if (!canManage(user)) {
    return NextResponse.json({ error: "Forbidden. Managers, HR, or admin only." }, { status: 403 });
  }

  const db = getDb();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "Invalid application id." }, { status: 400 });
  }

  const app = db.prepare("SELECT * FROM applications WHERE id = ?").get(id) as Application | undefined;
  if (!app) {
    return NextResponse.json({ error: "Application not found." }, { status: 404 });
  }

  let body: { stage?: string; notes?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const updates: string[] = [];
  const args: (string | null | number)[] = [];

  if (body.stage !== undefined) {
    const nextStage = body.stage as ApplicationStage;
    const allowed = VALID_NEXT[app.stage];
    if (!allowed || !allowed.includes(nextStage)) {
      return NextResponse.json(
        { error: `Cannot move from '${app.stage}' to '${nextStage}'.` },
        { status: 400 }
      );
    }
    updates.push("stage = ?");
    args.push(nextStage);
    logAudit(user.id, "stage_change", "application", id, `${app.stage} → ${nextStage}`);
  }

  if (body.notes !== undefined) {
    updates.push("notes = ?");
    args.push(typeof body.notes === "string" && body.notes.trim() ? body.notes.trim() : null);
  }

  if (updates.length > 0) {
    updates.push("updated_at = datetime('now')");
    args.push(id);
    db.prepare(`UPDATE applications SET ${updates.join(", ")} WHERE id = ?`).run(...args);
    if (!body.stage) {
      logAudit(user.id, "update", "application", id, "notes updated");
    }
  }

  return NextResponse.json({ id, ok: true });
}
