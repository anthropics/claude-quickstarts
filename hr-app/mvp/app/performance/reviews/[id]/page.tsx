import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import type { Employee, Review, ReviewCycle } from "@/lib/types";
import ReviewForm from "../../_components/ReviewForm";
import { REVIEW_STATUS_BADGE, REVIEW_STATUS_LABEL, canViewReview, ratingStars } from "../../_lib/perf";

export const dynamic = "force-dynamic";

export default function ReviewDetailPage({ params }: { params: { id: string } }) {
  const db = getDb();
  const user = getCurrentUser();

  const id = Number(params.id);
  if (!Number.isInteger(id)) notFound();

  const review = db.prepare("SELECT * FROM reviews WHERE id = ?").get(id) as Review | undefined;
  if (!review) notFound();

  const employee = db.prepare("SELECT * FROM employees WHERE id = ?").get(review.employee_id) as
    | Employee
    | undefined;
  const reviewer = db.prepare("SELECT * FROM employees WHERE id = ?").get(review.reviewer_id) as
    | Employee
    | undefined;
  const cycle = db.prepare("SELECT * FROM review_cycles WHERE id = ?").get(review.cycle_id) as
    | ReviewCycle
    | undefined;
  if (!employee || !reviewer || !cycle) notFound();

  if (!canViewReview(user, review, employee)) notFound();

  const editable =
    review.reviewer_id === user.id && (review.status === "pending" || review.status === "in_progress");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">
            {review.type === "self" ? "Self review" : "Manager review"} — {employee.first_name} {employee.last_name}
          </h1>
          <p className="text-sm text-gray-500">
            {cycle.name} · {cycle.period_start} → {cycle.period_end}
          </p>
        </div>
        <Link href="/performance/reviews" className="btn-secondary text-sm">← My reviews</Link>
      </div>

      <div className="card">
        <div className="grid gap-4 sm:grid-cols-4">
          <div>
            <p className="label mb-0">Employee</p>
            <p className="text-sm font-medium">{employee.first_name} {employee.last_name}</p>
          </div>
          <div>
            <p className="label mb-0">Reviewer</p>
            <p className="text-sm font-medium">{reviewer.first_name} {reviewer.last_name}</p>
          </div>
          <div>
            <p className="label mb-0">Type</p>
            <p className="text-sm font-medium">{review.type === "self" ? "Self review" : "Manager review"}</p>
          </div>
          <div>
            <p className="label mb-0">Status</p>
            <span className={REVIEW_STATUS_BADGE[review.status]}>{REVIEW_STATUS_LABEL[review.status]}</span>
          </div>
        </div>
      </div>

      {editable ? (
        <ReviewForm
          reviewId={review.id}
          initialStrengths={review.strengths}
          initialImprovements={review.improvements}
          initialComments={review.overall_comments}
          initialRating={review.rating}
        />
      ) : (
        <div className="card space-y-5">
          <div>
            <p className="label">Rating</p>
            <p className="text-xl text-yellow-500" aria-label={review.rating ? `${review.rating} out of 5` : "No rating"}>
              {ratingStars(review.rating)}
              {review.rating !== null && <span className="ml-2 text-sm text-gray-500">{review.rating} / 5</span>}
            </p>
          </div>
          <div>
            <p className="label">Strengths</p>
            <p className="whitespace-pre-wrap text-sm text-gray-700">{review.strengths ?? "—"}</p>
          </div>
          <div>
            <p className="label">Areas for improvement</p>
            <p className="whitespace-pre-wrap text-sm text-gray-700">{review.improvements ?? "—"}</p>
          </div>
          <div>
            <p className="label">Overall comments</p>
            <p className="whitespace-pre-wrap text-sm text-gray-700">{review.overall_comments ?? "—"}</p>
          </div>
          {review.submitted_at && (
            <p className="text-xs text-gray-400">Submitted {review.submitted_at.slice(0, 16)}</p>
          )}
          {!review.submitted_at && (
            <p className="text-xs text-gray-400">This review has not been submitted yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
