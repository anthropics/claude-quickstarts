import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr, canManage } from "@/lib/session";
import PostingActions from "../_components/PostingActions";
import AddCandidateForm from "../_components/AddCandidateForm";
import type { JobPosting, ApplicationStage } from "@/lib/types";

export const dynamic = "force-dynamic";

const PIPELINE_STAGES: { key: ApplicationStage; label: string }[] = [
  { key: "applied", label: "Applied" },
  { key: "screening", label: "Screening" },
  { key: "phone_screen", label: "Phone Screen" },
  { key: "interview", label: "Interview" },
  { key: "assessment", label: "Assessment" },
  { key: "offer", label: "Offer" },
  { key: "hired", label: "Hired" },
  { key: "rejected", label: "Rejected" },
];

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

interface AppCard {
  app_id: number;
  stage: ApplicationStage;
  first_name: string;
  last_name: string;
  source: string;
  created_at: string;
  avg_rating: number | null;
}

export default function JobPostingDetailPage({ params }: { params: { id: string } }) {
  const db = getDb();
  const user = getCurrentUser();
  const id = Number(params.id);

  const posting = db
    .prepare(
      `SELECT jp.*, d.name AS department_name
       FROM job_postings jp
       LEFT JOIN departments d ON d.id = jp.department_id
       WHERE jp.id = ?`
    )
    .get(id) as (JobPosting & { department_name: string | null }) | undefined;

  if (!posting) notFound();

  const userIsHr = isHr(user);
  const userCanManage = canManage(user);

  const appCards = db
    .prepare(
      `SELECT a.id AS app_id, a.stage, a.created_at,
              c.first_name, c.last_name, c.source,
              AVG(i.rating) AS avg_rating
       FROM applications a
       JOIN candidates c ON c.id = a.candidate_id
       LEFT JOIN interviews i ON i.application_id = a.id AND i.rating IS NOT NULL
       WHERE a.job_posting_id = ?
       GROUP BY a.id
       ORDER BY a.created_at DESC`
    )
    .all(id) as AppCard[];

  const byStage = new Map<string, AppCard[]>();
  for (const card of appCards) {
    const existing = byStage.get(card.stage) ?? [];
    existing.push(card);
    byStage.set(card.stage, existing);
  }

  const employmentTypeLabel: Record<string, string> = {
    full_time: "Full-time",
    part_time: "Part-time",
    contract: "Contract",
    intern: "Intern",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/recruitment" className="text-sm text-brand-600 hover:underline">
            ← Recruitment
          </Link>
          <h1 className="mt-1 text-2xl font-bold">{posting.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-600">
            {posting.department_name && <span>{posting.department_name}</span>}
            {posting.department_name && posting.location && <span>·</span>}
            {posting.location && <span>{posting.location}</span>}
            <span>·</span>
            <span>{employmentTypeLabel[posting.employment_type] ?? posting.employment_type}</span>
            <span>·</span>
            {statusBadge(posting.status)}
          </div>
          {posting.closes_at && (
            <p className="mt-1 text-xs text-gray-400">Closes {posting.closes_at}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {userIsHr && (
            <Link href={`/recruitment/${id}/edit`} className="btn-secondary">
              Edit
            </Link>
          )}
          <PostingActions postingId={id} status={posting.status} isHr={userIsHr} />
        </div>
      </div>

      {/* Description */}
      {(posting.description || posting.requirements) && (
        <div className="grid gap-4 lg:grid-cols-2">
          {posting.description && (
            <div className="card">
              <h2 className="mb-2 font-semibold">Description</h2>
              <p className="whitespace-pre-wrap text-sm text-gray-700">{posting.description}</p>
            </div>
          )}
          {posting.requirements && (
            <div className="card">
              <h2 className="mb-2 font-semibold">Requirements</h2>
              <p className="whitespace-pre-wrap text-sm text-gray-700">{posting.requirements}</p>
            </div>
          )}
        </div>
      )}

      {/* Add candidate */}
      {userIsHr && <AddCandidateForm postingId={id} />}

      {/* Kanban pipeline */}
      <div>
        <h2 className="mb-3 font-semibold">
          Pipeline{" "}
          <span className="ml-1 text-sm font-normal text-gray-500">({appCards.length} applicant{appCards.length !== 1 ? "s" : ""})</span>
        </h2>

        {appCards.length === 0 && !userIsHr && (
          <p className="text-sm text-gray-500">No applications yet.</p>
        )}

        <div className="overflow-x-auto pb-4">
          <div className="flex gap-3" style={{ minWidth: `${PIPELINE_STAGES.length * 14}rem` }}>
            {PIPELINE_STAGES.map(({ key, label }) => {
              const cards = byStage.get(key) ?? [];
              return (
                <div key={key} className="w-52 shrink-0">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                      {label}
                    </span>
                    <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600">
                      {cards.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {cards.map((card) => (
                      <Link
                        key={card.app_id}
                        href={`/recruitment/${id}/applications/${card.app_id}`}
                        className="block rounded-lg border border-gray-200 bg-white p-3 shadow-sm hover:border-brand-300 hover:shadow-md transition-shadow"
                      >
                        <p className="text-sm font-medium text-gray-900">
                          {card.first_name} {card.last_name}
                        </p>
                        <div className="mt-1 flex items-center justify-between gap-1">
                          {sourceBadge(card.source)}
                          {card.avg_rating != null && (
                            <span className="text-xs text-yellow-600">
                              {"★".repeat(Math.round(card.avg_rating))}
                              {"☆".repeat(5 - Math.round(card.avg_rating))}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-gray-400">
                          {card.created_at.slice(0, 10)}
                        </p>
                      </Link>
                    ))}
                    {cards.length === 0 && (
                      <div className="rounded-lg border border-dashed border-gray-200 p-3 text-center text-xs text-gray-400">
                        Empty
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
