import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import { uniqueConstraintMessage, validateEmployeePayload } from "./_lib/validation";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const db = getDb();
  const result = validateEmployeePayload(db, body, { partial: false });
  if ("error" in result) {
    return NextResponse.json({ error: result.error }, { status: 400 });
  }
  const d = result.data;

  try {
    const info = db
      .prepare(
        `INSERT INTO employees
           (employee_number, first_name, last_name, work_email, phone, job_title,
            department_id, manager_id, employment_type, start_date, probation_end_date, role)
         VALUES (@employee_number, @first_name, @last_name, @work_email, @phone, @job_title,
                 @department_id, @manager_id, @employment_type, @start_date, @probation_end_date, @role)`
      )
      .run({
        phone: null,
        department_id: null,
        manager_id: null,
        probation_end_date: null,
        ...d,
      });
    const id = Number(info.lastInsertRowid);
    logAudit(user.id, "employee.create", "employee", id, `Created ${d.first_name} ${d.last_name} (${d.employee_number})`);
    return NextResponse.json({ id }, { status: 201 });
  } catch (err) {
    const message = uniqueConstraintMessage(err);
    if (message) return NextResponse.json({ error: message }, { status: 409 });
    throw err;
  }
}
