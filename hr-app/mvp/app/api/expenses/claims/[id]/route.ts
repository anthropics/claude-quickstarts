import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { Employee, ExpenseClaim } from "@/lib/types";

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const db = getDb();

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid claim id." }, { status: 400 });
  }

  let body: { action?: string; note?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  const action = body.action;
  const note = typeof body.note === "string" && body.note.trim() ? body.note.trim() : null;

  const claim = db.prepare("SELECT * FROM expense_claims WHERE id = ?").get(id) as ExpenseClaim | undefined;
  if (!claim) {
    return NextResponse.json({ error: "Expense claim not found." }, { status: 404 });
  }

  if (action === "approve" || action === "reject") {
    if (claim.status !== "pending") {
      return NextResponse.json({ error: `Only pending claims can be ${action}d.` }, { status: 400 });
    }
    const owner = db.prepare("SELECT * FROM employees WHERE id = ?").get(claim.employee_id) as Employee | undefined;
    const isManagerOfOwner = owner?.manager_id === user.id;
    if (!isHr(user) && !isManagerOfOwner) {
      return NextResponse.json({ error: "You are not allowed to decide this claim." }, { status: 403 });
    }
    const status = action === "approve" ? "approved" : "rejected";
    db.prepare(
      `UPDATE expense_claims
       SET status = ?, approver_id = ?, decided_at = datetime('now'), decision_note = ?
       WHERE id = ?`
    ).run(status, user.id, note, id);
    logAudit(user.id, action, "expense_claim", id, note ?? undefined);
    return NextResponse.json({ id, status });
  }

  if (action === "reimburse") {
    if (!isHr(user)) {
      return NextResponse.json({ error: "Only HR can mark claims as reimbursed." }, { status: 403 });
    }
    if (claim.status !== "approved") {
      return NextResponse.json({ error: "Only approved claims can be marked as reimbursed." }, { status: 400 });
    }
    db.prepare(
      `UPDATE expense_claims
       SET status = 'reimbursed', decided_at = datetime('now'), decision_note = COALESCE(?, decision_note)
       WHERE id = ?`
    ).run(note, id);
    logAudit(user.id, "reimburse", "expense_claim", id, note ?? undefined);
    return NextResponse.json({ id, status: "reimbursed" });
  }

  return NextResponse.json({ error: "Unknown action. Use 'approve', 'reject' or 'reimburse'." }, { status: 400 });
}

export async function DELETE(_request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const db = getDb();

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid claim id." }, { status: 400 });
  }

  const claim = db.prepare("SELECT * FROM expense_claims WHERE id = ?").get(id) as ExpenseClaim | undefined;
  if (!claim) {
    return NextResponse.json({ error: "Expense claim not found." }, { status: 404 });
  }
  if (claim.employee_id !== user.id) {
    return NextResponse.json({ error: "Only the claim owner can delete it." }, { status: 403 });
  }
  if (claim.status !== "pending") {
    return NextResponse.json({ error: "Only pending claims can be deleted." }, { status: 400 });
  }

  db.prepare("DELETE FROM expense_claims WHERE id = ?").run(id);
  logAudit(user.id, "delete", "expense_claim", id);

  return NextResponse.json({ id, deleted: true });
}
