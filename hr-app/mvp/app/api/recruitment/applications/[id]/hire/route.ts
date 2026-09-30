import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import { notify } from "@/lib/notify";
import type { Application, Candidate, JobPosting, Offer } from "@/lib/types";

export const dynamic = "force-dynamic";

const ROLES = ["admin", "hr", "manager", "employee"];
const PROBATION_MONTHS = [0, 3, 6];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function addMonths(date: string, months: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + months);
  return d.toISOString().slice(0, 10);
}

/**
 * Converts a hired (or offer-accepted) applicant into an employee: creates the
 * employee row, an employment_history 'hired' entry, the BASIC salary from the
 * accepted offer, marks the application hired, and notifies the new manager.
 */
export async function POST(request: Request, { params }: { params: { id: string } }) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden. HR/admin only." }, { status: 403 });
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

  const candidate = db.prepare("SELECT * FROM candidates WHERE id = ?").get(app.candidate_id) as Candidate | undefined;
  const posting = db.prepare("SELECT * FROM job_postings WHERE id = ?").get(app.job_posting_id) as JobPosting | undefined;
  if (!candidate || !posting) {
    return NextResponse.json({ error: "Candidate or job posting not found." }, { status: 404 });
  }

  const acceptedOffer = db
    .prepare("SELECT * FROM offers WHERE application_id = ? AND status = 'accepted' ORDER BY created_at DESC LIMIT 1")
    .get(id) as Offer | undefined;

  const eligible = app.stage === "hired" || (app.stage === "offer" && !!acceptedOffer);
  if (!eligible) {
    return NextResponse.json(
      { error: "Only applications in stage 'hired', or 'offer' with an accepted offer, can be converted." },
      { status: 400 }
    );
  }

  let body: {
    employee_number?: string;
    manager_id?: number | null;
    role?: string;
    probation_months?: number;
    start_date?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const employee_number = typeof body.employee_number === "string" ? body.employee_number.trim() : "";
  if (!employee_number) {
    return NextResponse.json({ error: "employee_number is required." }, { status: 400 });
  }

  const role = typeof body.role === "string" ? body.role : "employee";
  if (!ROLES.includes(role)) {
    return NextResponse.json({ error: `role must be one of: ${ROLES.join(", ")}.` }, { status: 400 });
  }

  const probationMonths = body.probation_months ?? 0;
  if (!PROBATION_MONTHS.includes(probationMonths)) {
    return NextResponse.json({ error: "probation_months must be 0, 3 or 6." }, { status: 400 });
  }

  const start_date =
    typeof body.start_date === "string" && body.start_date.trim()
      ? body.start_date.trim()
      : acceptedOffer?.start_date ?? "";
  if (!DATE_RE.test(start_date)) {
    return NextResponse.json({ error: "start_date is required (YYYY-MM-DD)." }, { status: 400 });
  }

  let manager_id: number | null = null;
  if (body.manager_id !== undefined && body.manager_id !== null) {
    if (typeof body.manager_id !== "number" || !Number.isInteger(body.manager_id)) {
      return NextResponse.json({ error: "manager_id must be an integer or null." }, { status: 400 });
    }
    const manager = db.prepare("SELECT id FROM employees WHERE id = ?").get(body.manager_id);
    if (!manager) {
      return NextResponse.json({ error: "Selected manager does not exist." }, { status: 400 });
    }
    manager_id = body.manager_id;
  }

  // Conflicts (email is the candidate's — it becomes the work email).
  const emailTaken = db
    .prepare("SELECT id FROM employees WHERE lower(work_email) = lower(?)")
    .get(candidate.email);
  if (emailTaken) {
    return NextResponse.json(
      { error: `An employee already exists with the email ${candidate.email}.` },
      { status: 409 }
    );
  }
  const numberTaken = db.prepare("SELECT id FROM employees WHERE employee_number = ?").get(employee_number);
  if (numberTaken) {
    return NextResponse.json({ error: "That employee number is already in use." }, { status: 409 });
  }

  const probation_end_date = probationMonths > 0 ? addMonths(start_date, probationMonths) : null;

  const employeeId = db.transaction(() => {
    const info = db
      .prepare(
        `INSERT INTO employees
           (employee_number, first_name, last_name, work_email, phone, job_title,
            department_id, manager_id, employment_type, start_date, probation_end_date, status, role)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)`
      )
      .run(
        employee_number,
        candidate.first_name,
        candidate.last_name,
        candidate.email,
        candidate.phone,
        posting.title,
        posting.department_id,
        manager_id,
        posting.employment_type,
        start_date,
        probation_end_date,
        role
      );
    const employeeId = Number(info.lastInsertRowid);

    db.prepare(
      `INSERT INTO employment_history
         (employee_id, job_title, department_id, manager_id, employment_type, effective_from, change_reason)
       VALUES (?, ?, ?, ?, ?, ?, 'hired')`
    ).run(employeeId, posting.title, posting.department_id, manager_id, posting.employment_type, start_date);

    if (acceptedOffer) {
      const basicCode = db.prepare("SELECT id FROM earnings_codes WHERE code = 'BASIC'").get() as
        | { id: number }
        | undefined;
      if (basicCode) {
        db.prepare(
          `INSERT INTO employee_earnings (employee_id, earnings_code_id, amount, effective_from)
           VALUES (?, ?, ?, ?)`
        ).run(employeeId, basicCode.id, acceptedOffer.salary, start_date);
      }
    }

    if (app.stage !== "hired") {
      db.prepare("UPDATE applications SET stage = 'hired', updated_at = datetime('now') WHERE id = ?").run(id);
    }

    return employeeId;
  })();

  logAudit(user.id, "employee.create", "employee", employeeId,
    `Hired ${candidate.first_name} ${candidate.last_name} (${employee_number}) from application ${id}`);
  if (app.stage !== "hired") {
    logAudit(user.id, "stage_change", "application", id, `${app.stage} → hired`);
  }

  if (manager_id) {
    notify({
      employeeId: manager_id,
      type: "recruitment.hired",
      title: `New hire: ${candidate.first_name} ${candidate.last_name} joins your team`,
      body: `${candidate.first_name} ${candidate.last_name} starts as ${posting.title} on ${start_date}.`,
      link: `/employees/${employeeId}`,
    });
  }

  return NextResponse.json({ employee_id: employeeId }, { status: 201 });
}
