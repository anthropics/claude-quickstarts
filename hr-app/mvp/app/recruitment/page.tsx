import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

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

function statusBadge(status: string) {
  switch (status) {
    case "open":
      return <span className="badge-green">Open</span>;
    case "draft":
      return <span className="badge-gray">Draft</span>;
    case "closed":
      return <span className="badge-red">Closed</span>;
    case "on_hold":
      return <span className="badge-yellow">On Hold</span>;
    default:
      return <span className="badge-gray">{status}</span>;
  }
}

function employmentTypeLabel(type: string) {
  const labels: Record<string, string> = {
    full_time: "Full-time",
    part_time: "Part-time",
    contract: "Contract",
    intern: "Intern",
  };
  return labels[type] ?? type;
}

interface PostingRow {
  id: number;
  title: string;
  department: string | null;
  employment_type: string;
  status: string;
  posted_at: string | null;
  closes_at: string | null;
  app_count: number;
}

interface StageStat {
  stage: string;
  cnt: number;
}

export default function RecruitmentDashboard() {
  const db = getDb();
  const user = getCurrentUser();
  const today = new Date().toISOString().slice(0, 10);
  const weekEnd = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);

  const openRoles = (
    db.prepare("SELECT COUNT(*) AS n FROM job_postings WHERE status = 'open'").get() as { n: number }
  ).n;

  const activeApps = (
    db
      .prepare(
        `SELECT COUNT(*) AS n FROM applications
         WHERE stage NOT IN ('hired', 'rejected', 'withdrawn')`
      )
      .get() as { n: number }
  ).n;

  const interviewsThisWeek = (
    db
      .prepare(
        `SELECT COUNT(*) AS n FROM interviews
         WHERE date(scheduled_at) >= ? AND date(scheduled_at) <= ?`
      )
      .get(today, weekEnd) as { n: number }
  ).n;

  const stageStats = db
    .prepare(
      `SELECT stage, COUNT(*) AS cnt FROM applications
       WHERE stage NOT IN ('hired', 'rejected', 'withdrawn')
       GROUP BY stage ORDER BY cnt DESC`
    )
    .all() as StageStat[];

  const postings = db
    .prepare(
      `SELECT jp.id, jp.title, d.name AS department, jp.employment_type, jp.status,
              jp.posted_at, jp.closes_at,
              COUNT(a.id) AS app_count
       FROM job_postings jp
       LEFT JOIN departments d ON d.id = jp.department_id
       LEFT JOIN applications a ON a.job_posting_id = jp.id
       GROUP BY jp.id
       ORDER BY jp.created_at DESC`
    )
    .all() as PostingRow[];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Recruitment</h1>
          <p className="text-sm text-gray-500">Manage job postings, candidates, and the hiring pipeline.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/recruitment/candidates" className="btn-secondary text-sm">
            Candidates
          </Link>
          {isHr(user) && (
            <Link href="/recruitment/new" className="btn-primary text-sm">
              + New job posting
            </Link>
          )}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Open roles</p>
          <p className="mt-1 text-3xl font-bold">{openRoles}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Active applications</p>
          <p className="mt-1 text-3xl font-bold">{activeApps}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Interviews this week</p>
          <p className="mt-1 text-3xl font-bold">{interviewsThisWeek}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Pipeline by stage</p>
          <div className="mt-2 space-y-1">
            {stageStats.length === 0 && <p className="text-sm text-gray-400">No active apps</p>}
            {stageStats.slice(0, 4).map((s) => (
              <div key={s.stage} className="flex items-center justify-between">
                <span className="text-xs text-gray-600">{STAGE_LABELS[s.stage] ?? s.stage}</span>
                <span className="text-xs font-semibold">{s.cnt}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Job postings table */}
      <div className="card overflow-x-auto p-0">
        <div className="border-b border-gray-100 px-5 py-3">
          <h2 className="font-semibold">Job Postings</h2>
        </div>
        <table className="w-full min-w-[700px]">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Title</th>
              <th className="th">Department</th>
              <th className="th">Type</th>
              <th className="th">Status</th>
              <th className="th text-right">Applications</th>
              <th className="th">Posted</th>
              <th className="th">Closes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {postings.length === 0 && (
              <tr>
                <td className="td py-8 text-center text-gray-500" colSpan={7}>
                  No job postings yet.
                </td>
              </tr>
            )}
            {postings.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="td">
                  <Link
                    href={`/recruitment/${p.id}`}
                    className="font-medium text-brand-600 hover:underline"
                  >
                    {p.title}
                  </Link>
                </td>
                <td className="td">{p.department ?? "—"}</td>
                <td className="td">{employmentTypeLabel(p.employment_type)}</td>
                <td className="td">{statusBadge(p.status)}</td>
                <td className="td text-right">{p.app_count}</td>
                <td className="td">{p.posted_at ? p.posted_at.slice(0, 10) : "—"}</td>
                <td className="td">{p.closes_at ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
