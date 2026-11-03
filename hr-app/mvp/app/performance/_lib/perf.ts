import { isHr } from "@/lib/session";
import type { Employee, Goal, Review } from "@/lib/types";

/** Can `user` see / manage a goal owned by `ownerId` (whose manager is `ownerManagerId`)? */
export function canTouchGoal(user: Employee, ownerId: number, ownerManagerId: number | null): boolean {
  return user.id === ownerId || ownerManagerId === user.id || isHr(user);
}

/**
 * Review visibility: reviewer, HR and the reviewed employee's manager can
 * always view. The reviewed employee sees their own self review always, but a
 * manager review about them only once it has been submitted.
 */
export function canViewReview(user: Employee, review: Review, reviewedEmployee: Employee): boolean {
  if (isHr(user)) return true;
  if (user.id === review.reviewer_id) return true;
  if (reviewedEmployee.manager_id === user.id) return true;
  if (user.id === review.employee_id) {
    return review.type === "self" || review.status === "submitted" || review.status === "acknowledged";
  }
  return false;
}

export function goalProgressPct(goal: Pick<Goal, "metric_type" | "target_value" | "current_value">): number {
  if (goal.metric_type === "boolean") return goal.current_value >= goal.target_value ? 100 : 0;
  if (goal.target_value <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((goal.current_value / goal.target_value) * 100)));
}

export function goalProgressLabel(goal: Pick<Goal, "metric_type" | "target_value" | "current_value">): string {
  if (goal.metric_type === "boolean") return goal.current_value >= goal.target_value ? "Done" : "Not done";
  if (goal.metric_type === "percentage") return `${Math.round(goal.current_value)}%`;
  return `${goal.current_value.toLocaleString("en-US")} / ${goal.target_value.toLocaleString("en-US")}`;
}

export const GOAL_STATUS_BADGE: Record<Goal["status"], string> = {
  not_started: "badge-gray",
  in_progress: "badge-blue",
  at_risk: "badge-red",
  achieved: "badge-green",
  missed: "badge-red",
};

export const GOAL_STATUS_LABEL: Record<Goal["status"], string> = {
  not_started: "Not started",
  in_progress: "In progress",
  at_risk: "At risk",
  achieved: "Achieved",
  missed: "Missed",
};

export const REVIEW_STATUS_BADGE: Record<Review["status"], string> = {
  pending: "badge-gray",
  in_progress: "badge-yellow",
  submitted: "badge-green",
  acknowledged: "badge-blue",
};

export const REVIEW_STATUS_LABEL: Record<Review["status"], string> = {
  pending: "Pending",
  in_progress: "In progress",
  submitted: "Submitted",
  acknowledged: "Acknowledged",
};

export const CYCLE_STATUS_BADGE: Record<string, string> = {
  setup: "badge-yellow",
  active: "badge-green",
  closed: "badge-gray",
};

export const ONE_ON_ONE_STATUS_BADGE: Record<string, string> = {
  scheduled: "badge-blue",
  completed: "badge-green",
  cancelled: "badge-gray",
};

export function ratingStars(rating: number | null): string {
  if (!rating || rating < 1) return "—";
  const r = Math.min(5, Math.max(1, Math.round(rating)));
  return "★".repeat(r) + "☆".repeat(5 - r);
}

/** "2026-06-17 10:00:00" → "2026-06-17 10:00" */
export function fmtDateTime(dt: string): string {
  return dt.replace("T", " ").slice(0, 16);
}
