import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import { notify } from "@/lib/notify";
import { uniqueConstraintMessage, validateEmployeePayload } from "../_lib/validation";

export const dynamic = "force-dynamic";

/** Job fields that are versioned in employment_history rather than silently overwritten. */
const JOB_FIELDS = ["job_title", "department_id", "manager_id", "employment_type"] as const;
const CHANGE_REASONS = ["promotion", "transfer", "restructure", "correction"];

interface JobSnapshot {
  job_title: string;
  department_id: number | null;
  manager_id: number | null;
  employment_type: string;
}

export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "Invalid employee id." }, { status: 400 });
  }

  const db = getDb();
  const existing = db
    .prepare("SELECT id, job_title, department_id, manager_id, employment_type FROM employees WHERE id = ?")
    .get(id) as ({ id: number } & JobSnapshot) | undefined;
  if (!existing) {
    return NextResponse.json({ error: "Employee not found." }, { status: 404 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  // change_reason is versioning metadata, not an employee column.
  let changeReason = "correction";
  if (typeof body === "object" && body !== null && "change_reason" in body) {
    const raw = (body as Record<string, unknown>).change_reason;
    if (raw !== null && raw !== undefined && raw !== "") {
      if (typeof raw !== "string" || !CHANGE_REASONS.includes(raw)) {
        return NextResponse.json(
          { error: `change reason must be one of: ${CHANGE_REASONS.join(", ")}.` },
          { status: 400 }
        );
      }
      changeReason = raw;
    }
  }

  const result = validateEmployeePayload(db, body, { partial: true, selfId: id });
  if ("error" in result) {
    return NextResponse.json({ error: result.error }, { status: 400 });
  }
  const fields = Object.keys(result.data);
  if (fields.length === 0) {
    return NextResponse.json({ error: "No editable fields provided." }, { status: 400 });
  }

  // Which versioned job fields actually change with this update?
  const jobChanged = JOB_FIELDS.some(
    (f) => f in result.data && result.data[f] !== existing[f]
  );

  try {
    const applyUpdate = db.transaction(() => {
      const setClause = fields.map((f) => `${f} = @${f}`).join(", ");
      db.prepare(`UPDATE employees SET ${setClause}, updated_at = datetime('now') WHERE id = @__id`).run({
        ...result.data,
        __id: id,
      });

      if (jobChanged) {
        // Production behaviour: job changes are recorded, not overwritten —
        // close the open history row and open a new one effective today.
        const today = new Date().toISOString().slice(0, 10);
        const next: JobSnapshot = {
          job_title: (result.data.job_title as string | undefined) ?? existing.job_title,
          department_id:
            "department_id" in result.data
              ? (result.data.department_id as number | null)
              : existing.department_id,
          manager_id:
            "manager_id" in result.data ? (result.data.manager_id as number | null) : existing.manager_id,
          employment_type:
            (result.data.employment_type as string | undefined) ?? existing.employment_type,
        };
        db.prepare(
          "UPDATE employment_history SET effective_to = ? WHERE employee_id = ? AND effective_to IS NULL"
        ).run(today, id);
        db.prepare(
          `INSERT INTO employment_history
             (employee_id, job_title, department_id, manager_id, employment_type, effective_from, change_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?)`
        ).run(id, next.job_title, next.department_id, next.manager_id, next.employment_type, today, changeReason);
      }
    });
    applyUpdate();

    logAudit(user.id, "employee.update", "employee", id, `Updated fields: ${fields.join(", ")}`);
    if (jobChanged) {
      const newTitle = (result.data.job_title as string | undefined) ?? existing.job_title;
      logAudit(user.id, "employee.job_change", "employee", id, `Reason: ${changeReason}`);
      notify({
        employeeId: id,
        type: "employee.job_change",
        title: `Your role has been updated to ${newTitle}`,
        body: `Your employment record was updated (reason: ${changeReason}). View your profile for details.`,
        link: `/employees/${id}`,
      });
    }
    return NextResponse.json({ id });
  } catch (err) {
    const message = uniqueConstraintMessage(err);
    if (message) return NextResponse.json({ error: message }, { status: 409 });
    throw err;
  }
}
