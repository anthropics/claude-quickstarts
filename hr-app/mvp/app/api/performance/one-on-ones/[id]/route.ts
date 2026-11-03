import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { OneOnOne } from "@/lib/types";

const STATUSES = ["scheduled", "completed", "cancelled"];

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const db = getDb();

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid meeting id." }, { status: 400 });
  }

  let body: { agenda?: unknown; notes?: unknown; action_items?: unknown; status?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const meeting = db.prepare("SELECT * FROM one_on_ones WHERE id = ?").get(id) as OneOnOne | undefined;
  if (!meeting) {
    return NextResponse.json({ error: "1-on-1 not found." }, { status: 404 });
  }
  if (meeting.manager_id !== user.id && meeting.employee_id !== user.id && !isHr(user)) {
    return NextResponse.json({ error: "Only participants can update this 1-on-1." }, { status: 403 });
  }

  const sets: string[] = [];
  const values: (string | null)[] = [];
  const detail: string[] = [];

  if (body.agenda !== undefined) {
    const agenda = typeof body.agenda === "string" && body.agenda.trim() ? body.agenda.trim() : null;
    sets.push("agenda = ?");
    values.push(agenda);
    detail.push("agenda");
  }

  if (body.notes !== undefined) {
    const notes = typeof body.notes === "string" && body.notes.trim() ? body.notes.trim() : null;
    sets.push("notes = ?");
    values.push(notes);
    detail.push("notes");
  }

  if (body.action_items !== undefined) {
    if (!Array.isArray(body.action_items)) {
      return NextResponse.json({ error: "action_items must be an array." }, { status: 400 });
    }
    const items: { text: string; done: boolean }[] = [];
    for (const item of body.action_items) {
      if (typeof item !== "object" || item === null || typeof (item as { text?: unknown }).text !== "string") {
        return NextResponse.json(
          { error: "Each action item needs a text field and an optional done flag." },
          { status: 400 }
        );
      }
      const text = ((item as { text: string }).text ?? "").trim();
      if (!text) continue;
      items.push({ text, done: Boolean((item as { done?: unknown }).done) });
    }
    sets.push("action_items = ?");
    values.push(JSON.stringify(items));
    detail.push("action_items");
  }

  if (body.status !== undefined) {
    if (typeof body.status !== "string" || !STATUSES.includes(body.status)) {
      return NextResponse.json({ error: "Invalid status." }, { status: 400 });
    }
    sets.push("status = ?");
    values.push(body.status);
    detail.push(`status=${body.status}`);
  }

  if (sets.length === 0) {
    return NextResponse.json({ error: "Nothing to update." }, { status: 400 });
  }

  db.prepare(`UPDATE one_on_ones SET ${sets.join(", ")} WHERE id = ?`).run(...values, id);
  logAudit(user.id, "update", "one_on_one", id, detail.join(", "));
  return NextResponse.json({ id });
}
