import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import { notify } from "@/lib/notify";
import type { Employee, LeaveRequest } from "@/lib/types";

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const db = getDb();

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid request id." }, { status: 400 });
  }

  let body: { action?: string; decision_note?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  const action = body.action;
  const decisionNote =
    typeof body.decision_note === "string" && body.decision_note.trim() ? body.decision_note.trim() : null;

  const req = db.prepare("SELECT * FROM leave_requests WHERE id = ?").get(id) as LeaveRequest | undefined;
  if (!req) {
    return NextResponse.json({ error: "Leave request not found." }, { status: 404 });
  }
  if (req.status !== "pending") {
    return NextResponse.json({ error: `Only pending requests can be ${action ?? "change"}d.` }, { status: 400 });
  }

  if (action === "cancel") {
    if (req.employee_id !== user.id) {
      return NextResponse.json({ error: "Only the request owner can cancel it." }, { status: 403 });
    }
    db.prepare("UPDATE leave_requests SET status = 'cancelled' WHERE id = ?").run(id);
    logAudit(user.id, "cancel", "leave_request", id);
    return NextResponse.json({ id, status: "cancelled" });
  }

  if (action === "approve" || action === "reject") {
    const owner = db.prepare("SELECT * FROM employees WHERE id = ?").get(req.employee_id) as Employee | undefined;
    const isManagerOfOwner = owner?.manager_id === user.id;
    if (!isHr(user) && !isManagerOfOwner) {
      return NextResponse.json({ error: "You are not allowed to decide this request." }, { status: 403 });
    }
    const status = action === "approve" ? "approved" : "rejected";
    db.prepare(
      `UPDATE leave_requests
       SET status = ?, approver_id = ?, decided_at = datetime('now'), decision_note = ?
       WHERE id = ?`
    ).run(status, user.id, decisionNote, id);
    logAudit(user.id, action, "leave_request", id, decisionNote ?? undefined);

    const typeName = (db.prepare("SELECT name FROM leave_types WHERE id = ?").get(req.leave_type_id) as { name: string } | undefined)?.name ?? "Leave";
    const range = req.start_date === req.end_date ? req.start_date : `${req.start_date} to ${req.end_date}`;
    notify({
      employeeId: req.employee_id,
      type: `leave.${status}`,
      title: `Your leave request was ${status}`,
      body: `${typeName}: ${range} — ${status} by ${user.first_name} ${user.last_name}.${decisionNote ? ` Note: ${decisionNote}` : ""}`,
      link: "/leave",
    });

    return NextResponse.json({ id, status });
  }

  return NextResponse.json({ error: "Unknown action. Use 'approve', 'reject' or 'cancel'." }, { status: 400 });
}
