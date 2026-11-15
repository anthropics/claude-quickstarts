import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import HireForm from "@/app/recruitment/_components/HireForm";
import type { Application, Candidate, Offer } from "@/lib/types";

export const dynamic = "force-dynamic";

/** Suggests the next EMPnnn number based on the current maximum. */
function suggestEmployeeNumber(numbers: string[]): string {
  let max = 0;
  for (const n of numbers) {
    const m = /^EMP(\d+)$/.exec(n);
    if (m) max = Math.max(max, Number(m[1]));
  }
  return `EMP${String(max + 1).padStart(3, "0")}`;
}

export default function HirePage({ params }: { params: { id: string; appId: string } }) {
  const user = getCurrentUser();
  const postingId = Number(params.id);
  const appId = Number(params.appId);
  const db = getDb();

  const app = db
    .prepare(
      `SELECT a.*, c.first_name, c.last_name, c.email, c.phone,
              jp.title AS job_title, jp.department_id AS posting_department_id,
              d.name AS department_name, d.head_employee_id
       FROM applications a
       JOIN candidates c ON c.id = a.candidate_id
       JOIN job_postings jp ON jp.id = a.job_posting_id
       LEFT JOIN departments d ON d.id = jp.department_id
       WHERE a.id = ? AND a.job_posting_id = ?`
    )
    .get(appId, postingId) as
    | (Application &
        Pick<Candidate, "first_name" | "last_name" | "email" | "phone"> & {
          job_title: string;
          posting_department_id: number | null;
          department_name: string | null;
          head_employee_id: number | null;
        })
    | undefined;

  if (!app) notFound();

  const backLink = `/recruitment/${postingId}/applications/${appId}`;

  if (!isHr(user)) {
    return (
      <div className="card max-w-2xl text-sm text-gray-500">
        Converting a candidate to an employee is restricted to HR and admins.{" "}
        <Link href={backLink} className="text-brand-600 hover:underline">Back to application</Link>
      </div>
    );
  }

  const acceptedOffer = db
    .prepare("SELECT * FROM offers WHERE application_id = ? AND status = 'accepted' ORDER BY created_at DESC LIMIT 1")
    .get(appId) as Offer | undefined;

  const eligible = app.stage === "hired" || (app.stage === "offer" && !!acceptedOffer);

  const existingEmployee = db
    .prepare("SELECT id, first_name, last_name FROM employees WHERE lower(work_email) = lower(?)")
    .get(app.email) as { id: number; first_name: string; last_name: string } | undefined;

  const header = (
    <div>
      <Link href={backLink} className="text-sm text-brand-600 hover:underline">
        ← {app.first_name} {app.last_name}
      </Link>
      <h1 className="mt-1 text-2xl font-bold">Convert to employee</h1>
      <p className="mt-1 text-sm text-gray-500">
        {app.job_title}
        {app.department_name ? ` · ${app.department_name}` : ""}
      </p>
    </div>
  );

  if (existingEmployee) {
    return (
      <div className="max-w-2xl space-y-6">
        {header}
        <div className="card border-green-200 bg-green-50 text-sm text-green-800">
          {app.first_name} {app.last_name} has already been converted —{" "}
          <Link href={`/employees/${existingEmployee.id}`} className="font-medium underline">
            view the employee profile
          </Link>
          .
        </div>
      </div>
    );
  }

  if (!eligible) {
    return (
      <div className="max-w-2xl space-y-6">
        {header}
        <div className="card text-sm text-gray-600">
          Only applications in stage <strong>hired</strong>, or <strong>offer</strong> with an
          accepted offer, can be converted to an employee.{" "}
          <Link href={backLink} className="text-brand-600 hover:underline">Back to application</Link>
        </div>
      </div>
    );
  }

  const employees = db
    .prepare(
      "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status = 'active' ORDER BY first_name, last_name"
    )
    .all() as { id: number; name: string }[];

  const allNumbers = (db.prepare("SELECT employee_number FROM employees").all() as { employee_number: string }[]).map(
    (r) => r.employee_number
  );

  return (
    <div className="max-w-2xl space-y-6">
      {header}
      <div className="card">
        <HireForm
          appId={appId}
          candidateName={`${app.first_name} ${app.last_name}`}
          candidateEmail={app.email}
          jobTitle={app.job_title}
          departmentName={app.department_name}
          salary={acceptedOffer?.salary ?? null}
          suggestedEmployeeNumber={suggestEmployeeNumber(allNumbers)}
          defaultStartDate={acceptedOffer?.start_date ?? new Date().toISOString().slice(0, 10)}
          defaultManagerId={app.head_employee_id}
          employees={employees}
        />
      </div>
    </div>
  );
}
