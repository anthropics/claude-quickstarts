import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr, canManage } from "@/lib/session";
import StageActions from "@/app/recruitment/_components/StageActions";
import NotesEditor from "@/app/recruitment/_components/NotesEditor";
import ScheduleInterviewForm from "@/app/recruitment/_components/ScheduleInterviewForm";
import CreateOfferForm from "@/app/recruitment/_components/CreateOfferForm";
import SendEmailForm from "@/app/recruitment/_components/SendEmailForm";
import type { Application, Candidate, JobPosting, Interview, Offer, ApplicationStage } from "@/lib/types";

export const dynamic = "force-dynamic";

const STAGE_LABELS: Record<string, string> = {
  applied: "Applied",
  screening: "Screening",
  phone_screen: "Phone Screen",
  interview: "Interview",
  assessment: "Assessment",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

function stageBadge(stage: string) {
  switch (stage) {
    case "hired":
      return <span className="badge-green">{STAGE_LABELS[stage]}</span>;
    case "rejected":
    case "withdrawn":
      return <span className="badge-red">{STAGE_LABELS[stage]}</span>;
    case "offer":
      return <span className="badge-blue">{STAGE_LABELS[stage]}</span>;
    default:
      return <span className="badge-yellow">{STAGE_LABELS[stage] ?? stage}</span>;
  }
}

function offerStatusBadge(status: string) {
  switch (status) {
    case "accepted":
      return <span className="badge-green">Accepted</span>;
    case "rejected":
    case "expired":
      return <span className="badge-red">{status.charAt(0).toUpperCase() + status.slice(1)}</span>;
    case "sent":
      return <span className="badge-blue">Sent</span>;
    default:
      return <span className="badge-gray">Draft</span>;
  }
}

function sourceBadge(source: string) {
  switch (source) {
    case "linkedin":
      return <span className="badge-blue">LinkedIn</span>;
    case "indeed":
      return <span className="badge-yellow">Indeed</span>;
    case "referral":
      return <span className="badge-green">Referral</span>;
    case "internal":
      return <span className="badge-blue">Internal</span>;
    case "careers":
      return <span className="badge-green">Careers site</span>;
    default:
      return <span className="badge-gray">Direct</span>;
  }
}

interface EmployeeRow {
  id: number;
  name: string;
}

export default function ApplicationDetailPage({
  params,
}: {
  params: { id: string; appId: string };
}) {
  const db = getDb();
  const user = getCurrentUser();
  const postingId = Number(params.id);
  const appId = Number(params.appId);

  const app = db
    .prepare(
      `SELECT a.*, c.first_name, c.last_name, c.email, c.phone, c.cv_filename, c.cv_file_id, c.source,
              jp.title AS job_title
       FROM applications a
       JOIN candidates c ON c.id = a.candidate_id
       JOIN job_postings jp ON jp.id = a.job_posting_id
       WHERE a.id = ? AND a.job_posting_id = ?`
    )
    .get(appId, postingId) as
    | (Application &
        Candidate & { job_title: string; cv_file_id: number | null; app_id?: number })
    | undefined;

  if (!app) notFound();

  const userIsHr = isHr(user);
  const userCanManage = canManage(user);

  const interviews = db
    .prepare("SELECT * FROM interviews WHERE application_id = ? ORDER BY scheduled_at ASC")
    .all(appId) as Interview[];

  const offer = db
    .prepare("SELECT * FROM offers WHERE application_id = ? ORDER BY created_at DESC LIMIT 1")
    .get(appId) as Offer | undefined;

  // Hired → employee conversion: offered-and-accepted or already-hired applications.
  const hiredEmployee = db
    .prepare("SELECT id FROM employees WHERE lower(work_email) = lower(?)")
    .get(app.email) as { id: number } | undefined;
  const canConvert =
    userIsHr &&
    !hiredEmployee &&
    (app.stage === "hired" || (app.stage === "offer" && offer?.status === "accepted"));

  const employees = db
    .prepare(
      "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status = 'active' ORDER BY first_name, last_name"
    )
    .all() as EmployeeRow[];

  const employeeMap = new Map<number, string>(employees.map((e) => [e.id, e.name]));

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Breadcrumb */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href={`/recruitment/${postingId}`} className="text-sm text-brand-600 hover:underline">
            ← {app.job_title}
          </Link>
          <h1 className="mt-1 text-2xl font-bold">
            {app.first_name} {app.last_name}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            {stageBadge(app.stage)}
            {sourceBadge(app.source)}
            <span className="text-sm text-gray-500">Applied {app.created_at.slice(0, 10)}</span>
          </div>
        </div>
        {canConvert && (
          <Link href={`/recruitment/${postingId}/applications/${appId}/hire`} className="btn-primary">
            Convert to employee
          </Link>
        )}
        {userIsHr && hiredEmployee && (
          <Link href={`/employees/${hiredEmployee.id}`} className="btn-secondary">
            View employee profile
          </Link>
        )}
      </div>

      {/* Candidate info */}
      <div className="card">
        <h2 className="mb-3 font-semibold">Candidate information</h2>
        <dl className="grid gap-3 sm:grid-cols-2 text-sm">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Email</dt>
            <dd className="mt-0.5 text-gray-900">{app.email}</dd>
          </div>
          {app.phone && (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Phone</dt>
              <dd className="mt-0.5 text-gray-900">{app.phone}</dd>
            </div>
          )}
          {(app.cv_file_id || app.cv_filename) && (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">CV</dt>
              <dd className="mt-0.5 text-gray-900">
                {app.cv_file_id ? (
                  <a
                    href={`/api/files/${app.cv_file_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-brand-600 hover:underline"
                  >
                    View CV{app.cv_filename ? ` (${app.cv_filename})` : ""}
                  </a>
                ) : (
                  app.cv_filename
                )}
              </dd>
            </div>
          )}
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Source</dt>
            <dd className="mt-0.5">{sourceBadge(app.source)}</dd>
          </div>
        </dl>
      </div>

      {/* Current stage & actions */}
      {userCanManage && (
        <div className="card">
          <h2 className="mb-3 font-semibold">Stage</h2>
          <p className="mb-3 text-sm text-gray-600">
            Current stage: {stageBadge(app.stage)}
          </p>
          <StageActions appId={appId} currentStage={app.stage as ApplicationStage} />
        </div>
      )}

      {/* Notes */}
      <div className="card">
        <NotesEditor appId={appId} initialNotes={app.notes} />
      </div>

      {/* Interviews section */}
      {(app.stage === "interview" || interviews.length > 0) && (
        <div className="card">
          <h2 className="mb-3 font-semibold">Interviews</h2>
          {interviews.length === 0 && (
            <p className="text-sm text-gray-500 mb-3">No interviews scheduled yet.</p>
          )}
          {interviews.length > 0 && (
            <div className="mb-4 space-y-4">
              {interviews.map((intv) => {
                const interviewerIds = JSON.parse(intv.interviewer_ids) as number[];
                const interviewerNames = interviewerIds.map((id) => employeeMap.get(id) ?? `Employee #${id}`);
                return (
                  <div key={intv.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium">
                          {intv.scheduled_at.replace("T", " ").slice(0, 16)}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {intv.duration_minutes} min ·{" "}
                          {intv.format === "video" ? "Video call" : intv.format === "in_person" ? "In person" : "Phone"}
                        </p>
                      </div>
                      {intv.rating != null && (
                        <div className="text-yellow-600 text-sm">
                          {"★".repeat(intv.rating)}{"☆".repeat(5 - intv.rating)}{" "}
                          <span className="text-gray-500 text-xs">({intv.rating}/5)</span>
                        </div>
                      )}
                    </div>
                    {interviewerNames.length > 0 && (
                      <p className="mt-1 text-xs text-gray-600">
                        Interviewers: {interviewerNames.join(", ")}
                      </p>
                    )}
                    {intv.notes && (
                      <p className="mt-1 text-xs text-gray-600 italic">{intv.notes}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {userCanManage && (
            <ScheduleInterviewForm appId={appId} employees={employees} />
          )}
        </div>
      )}

      {/* Offer section */}
      {(app.stage === "offer" || app.stage === "hired" || offer) && (
        <div className="card">
          <h2 className="mb-3 font-semibold">Offer</h2>
          {offer ? (
            <div className="space-y-3">
              <dl className="grid gap-3 sm:grid-cols-2 text-sm">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Salary</dt>
                  <dd className="mt-0.5 font-semibold text-gray-900">
                    R {offer.salary.toLocaleString("en-ZA")} / month
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Status</dt>
                  <dd className="mt-0.5">{offerStatusBadge(offer.status)}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Start date</dt>
                  <dd className="mt-0.5 text-gray-900">{offer.start_date}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Offer expiry</dt>
                  <dd className="mt-0.5 text-gray-900">{offer.expiry_date}</dd>
                </div>
              </dl>
              {offer.notes && (
                <p className="text-sm text-gray-600 italic">{offer.notes}</p>
              )}
            </div>
          ) : (
            <div>
              <p className="text-sm text-gray-500 mb-2">No offer created yet.</p>
              {userIsHr && <CreateOfferForm appId={appId} />}
            </div>
          )}
        </div>
      )}

      {/* Candidate communications */}
      {userIsHr && (
        <div className="card">
          <h2 className="mb-1 font-semibold">Send email</h2>
          <p className="mb-3 text-sm text-gray-500">
            Queue a templated email to the candidate. Sent emails are recorded in the notes.
          </p>
          <SendEmailForm appId={appId} candidateEmail={app.email} />
        </div>
      )}
    </div>
  );
}
