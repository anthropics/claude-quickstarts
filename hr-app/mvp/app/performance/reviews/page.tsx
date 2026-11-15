import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import { REVIEW_STATUS_BADGE, REVIEW_STATUS_LABEL, ratingStars } from "../_lib/perf";

export const dynamic = "force-dynamic";

interface ReviewRow {
  id: number;
  type: "self" | "manager";
  status: "pending" | "in_progress" | "submitted" | "acknowledged";
  rating: number | null;
  reviewer_id: number;
  employee_id: number;
  submitted_at: string | null;
  cycle_name: string;
  cycle_status: string;
  reviewer_name: string;
  employee_name: string;
}

export default function ReviewsPage() {
  const db = getDb();
  const user = getCurrentUser();

  const reviewsOfMe = db
    .prepare(
      `SELECT r.id, r.type, r.status, r.rating, r.reviewer_id, r.employee_id, r.submitted_at,
              c.name AS cycle_name, c.status AS cycle_status,
              rv.first_name || ' ' || rv.last_name AS reviewer_name,
              e.first_name || ' ' || e.last_name AS employee_name
       FROM reviews r
       JOIN review_cycles c ON c.id = r.cycle_id
       JOIN employees rv ON rv.id = r.reviewer_id
       JOIN employees e ON e.id = r.employee_id
       WHERE r.employee_id = ?
       ORDER BY c.period_start DESC, r.type`
    )
    .all(user.id) as ReviewRow[];

  const reviewsToWrite = db
    .prepare(
      `SELECT r.id, r.type, r.status, r.rating, r.reviewer_id, r.employee_id, r.submitted_at,
              c.name AS cycle_name, c.status AS cycle_status,
              rv.first_name || ' ' || rv.last_name AS reviewer_name,
              e.first_name || ' ' || e.last_name AS employee_name
       FROM reviews r
       JOIN review_cycles c ON c.id = r.cycle_id
       JOIN employees rv ON rv.id = r.reviewer_id
       JOIN employees e ON e.id = r.employee_id
       WHERE r.reviewer_id = ? AND r.status IN ('pending', 'in_progress')
       ORDER BY c.period_start DESC, r.type`
    )
    .all(user.id) as ReviewRow[];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">My reviews</h1>
          <p className="text-sm text-gray-500">Reviews about you and reviews you need to write.</p>
        </div>
        <Link href="/performance" className="btn-secondary text-sm">← Performance overview</Link>
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Reviews of me</h2>
        {reviewsOfMe.length === 0 ? (
          <p className="text-sm text-gray-500">No reviews yet — they will appear here once a cycle is launched.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {reviewsOfMe.map((r) => {
              const visible = r.type === "self" || r.status === "submitted" || r.status === "acknowledged";
              return (
                <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div>
                    <p className="text-sm font-medium">
                      {r.type === "self" ? "Self review" : `Manager review by ${r.reviewer_name}`}
                    </p>
                    <p className="text-xs text-gray-500">{r.cycle_name}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {visible && r.rating !== null && (
                      <span className="text-sm text-yellow-500" aria-label={`Rating ${r.rating} out of 5`}>
                        {ratingStars(r.rating)}
                      </span>
                    )}
                    <span className={REVIEW_STATUS_BADGE[r.status]}>{REVIEW_STATUS_LABEL[r.status]}</span>
                    {visible ? (
                      <Link href={`/performance/reviews/${r.id}`} className="text-sm font-medium text-brand-600 hover:underline">
                        View
                      </Link>
                    ) : (
                      <span className="text-xs text-gray-400">Hidden until submitted</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Reviews I need to write</h2>
        {reviewsToWrite.length === 0 ? (
          <p className="text-sm text-gray-500">You&apos;re all caught up — nothing to write.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {reviewsToWrite.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                <div>
                  <p className="text-sm font-medium">
                    {r.employee_id === user.id
                      ? "My self review"
                      : `${r.type === "self" ? "Self" : "Manager"} review of ${r.employee_name}`}
                  </p>
                  <p className="text-xs text-gray-500">{r.cycle_name}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={REVIEW_STATUS_BADGE[r.status]}>{REVIEW_STATUS_LABEL[r.status]}</span>
                  <Link href={`/performance/reviews/${r.id}`} className="text-sm font-medium text-brand-600 hover:underline">
                    {r.status === "pending" ? "Start" : "Continue"}
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
