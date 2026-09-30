import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import type { Goal, ReviewCycle } from "@/lib/types";
import GoalProgressBar from "./_components/GoalProgressBar";
import {
  GOAL_STATUS_BADGE,
  GOAL_STATUS_LABEL,
  REVIEW_STATUS_BADGE,
  REVIEW_STATUS_LABEL,
  fmtDateTime,
} from "./_lib/perf";

export const dynamic = "force-dynamic";

interface ReviewRow {
  id: number;
  type: "self" | "manager";
  status: "pending" | "in_progress" | "submitted" | "acknowledged";
  reviewer_id: number;
  employee_id: number;
  cycle_name: string;
  employee_name: string;
}

interface MeetingRow {
  id: number;
  scheduled_at: string;
  agenda: string | null;
  other_name: string;
}

interface GoalRow extends Goal {
  employee_name: string;
}

export default function PerformancePage() {
  const db = getDb();
  const user = getCurrentUser();
  const userCanManage = canManage(user);
  const userIsHr = isHr(user);

  // ── My data ────────────────────────────────────────────────────────────────
  const myGoals = db
    .prepare("SELECT * FROM goals WHERE employee_id = ? ORDER BY (due_date IS NULL), due_date")
    .all(user.id) as Goal[];

  const myOpenReviews = db
    .prepare(
      `SELECT r.id, r.type, r.status, r.reviewer_id, r.employee_id,
              c.name AS cycle_name, e.first_name || ' ' || e.last_name AS employee_name
       FROM reviews r
       JOIN review_cycles c ON c.id = r.cycle_id
       JOIN employees e ON e.id = r.employee_id
       WHERE r.employee_id = ? AND r.status IN ('pending', 'in_progress')
       ORDER BY r.id`
    )
    .all(user.id) as ReviewRow[];

  const myUpcoming = db
    .prepare(
      `SELECT o.id, o.scheduled_at, o.agenda, m.first_name || ' ' || m.last_name AS other_name
       FROM one_on_ones o JOIN employees m ON m.id = o.manager_id
       WHERE o.employee_id = ? AND o.status = 'scheduled'
       ORDER BY o.scheduled_at`
    )
    .all(user.id) as MeetingRow[];

  // ── Manager data ───────────────────────────────────────────────────────────
  const reportsGoals = userCanManage
    ? (db
        .prepare(
          `SELECT g.*, e.first_name || ' ' || e.last_name AS employee_name
           FROM goals g JOIN employees e ON e.id = g.employee_id
           WHERE e.manager_id = ?
           ORDER BY e.first_name, (g.due_date IS NULL), g.due_date`
        )
        .all(user.id) as GoalRow[])
    : [];

  const reviewsToWrite = userCanManage
    ? (db
        .prepare(
          `SELECT r.id, r.type, r.status, r.reviewer_id, r.employee_id,
                  c.name AS cycle_name, e.first_name || ' ' || e.last_name AS employee_name
           FROM reviews r
           JOIN review_cycles c ON c.id = r.cycle_id
           JOIN employees e ON e.id = r.employee_id
           WHERE r.reviewer_id = ? AND r.employee_id != ? AND r.status IN ('pending', 'in_progress')
           ORDER BY r.id`
        )
        .all(user.id, user.id) as ReviewRow[])
    : [];

  const managerMeetings = userCanManage
    ? (db
        .prepare(
          `SELECT o.id, o.scheduled_at, o.agenda, e.first_name || ' ' || e.last_name AS other_name
           FROM one_on_ones o JOIN employees e ON e.id = o.employee_id
           WHERE o.manager_id = ? AND o.status = 'scheduled'
           ORDER BY o.scheduled_at`
        )
        .all(user.id) as MeetingRow[])
    : [];

  // ── HR data ────────────────────────────────────────────────────────────────
  const activeCycle = userIsHr
    ? (db.prepare("SELECT * FROM review_cycles WHERE status = 'active' ORDER BY id DESC LIMIT 1").get() as
        | ReviewCycle
        | undefined)
    : undefined;
  const cycleCounts = activeCycle
    ? (db
        .prepare(
          `SELECT COUNT(*) AS total,
                  SUM(CASE WHEN status IN ('submitted', 'acknowledged') THEN 1 ELSE 0 END) AS submitted
           FROM reviews WHERE cycle_id = ?`
        )
        .get(activeCycle.id) as { total: number; submitted: number | null })
    : null;

  // ── Stat cards (scoped to goals visible to the user) ──────────────────────
  const goalScope = userIsHr ? "1=1" : userCanManage ? "(g.employee_id = @uid OR e.manager_id = @uid)" : "g.employee_id = @uid";
  const goalStats = db
    .prepare(
      `SELECT SUM(CASE WHEN g.status IN ('not_started', 'in_progress', 'at_risk') THEN 1 ELSE 0 END) AS active,
              SUM(CASE WHEN g.status = 'at_risk' THEN 1 ELSE 0 END) AS at_risk
       FROM goals g JOIN employees e ON e.id = g.employee_id
       WHERE ${goalScope}`
    )
    .get({ uid: user.id }) as { active: number | null; at_risk: number | null };

  const pendingReviewCount = (
    db
      .prepare("SELECT COUNT(*) AS n FROM reviews WHERE reviewer_id = ? AND status IN ('pending', 'in_progress')")
      .get(user.id) as { n: number }
  ).n;

  const upcomingMeetingCount = (
    db
      .prepare(
        "SELECT COUNT(*) AS n FROM one_on_ones WHERE (manager_id = ? OR employee_id = ?) AND status = 'scheduled'"
      )
      .get(user.id, user.id) as { n: number }
  ).n;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Performance</h1>
          <p className="text-sm text-gray-500">Goals, reviews and 1-on-1s in one place.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/performance/goals" className="btn-secondary text-sm">Goals</Link>
          <Link href="/performance/reviews" className="btn-secondary text-sm">Reviews</Link>
          <Link href="/performance/one-on-ones" className="btn-secondary text-sm">1-on-1s</Link>
          {userIsHr && <Link href="/performance/cycles" className="btn-secondary text-sm">Review cycles</Link>}
        </div>
      </div>

      {/* Summary stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Active goals</p>
          <p className="mt-1 text-3xl font-bold">{goalStats.active ?? 0}</p>
          <Link href="/performance/goals" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">View goals →</Link>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">At-risk goals</p>
          <p className="mt-1 text-3xl font-bold text-red-600">{goalStats.at_risk ?? 0}</p>
          <Link href="/performance/goals?status=at_risk" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">Review →</Link>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Pending reviews</p>
          <p className="mt-1 text-3xl font-bold">{pendingReviewCount}</p>
          <Link href="/performance/reviews" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">My reviews →</Link>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Upcoming 1-on-1s</p>
          <p className="mt-1 text-3xl font-bold">{upcomingMeetingCount}</p>
          <Link href="/performance/one-on-ones" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">View meetings →</Link>
        </div>
      </div>

      {/* HR section */}
      {userIsHr && (
        <div className="card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">Review cycle</h2>
              {activeCycle && cycleCounts ? (
                <p className="mt-1 text-sm text-gray-600">
                  <span className="font-medium">{activeCycle.name}</span> ({activeCycle.period_start} → {activeCycle.period_end}) —{" "}
                  {cycleCounts.submitted ?? 0} of {cycleCounts.total} reviews submitted
                </p>
              ) : (
                <p className="mt-1 text-sm text-gray-500">No active review cycle.</p>
              )}
            </div>
            <Link href="/performance/cycles" className="btn-secondary text-sm">Manage cycles</Link>
          </div>
          {activeCycle && cycleCounts && cycleCounts.total > 0 && (
            <div className="mt-3 h-2 rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-brand-600"
                style={{ width: `${Math.round(((cycleCounts.submitted ?? 0) / cycleCounts.total) * 100)}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* My section */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">My goals</h2>
            <Link href="/performance/goals" className="text-sm font-medium text-brand-600 hover:underline">All goals →</Link>
          </div>
          {myGoals.length === 0 ? (
            <p className="text-sm text-gray-500">No goals yet — create one on the goals page.</p>
          ) : (
            <div className="space-y-4">
              {myGoals.map((g) => (
                <div key={g.id} className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{g.title}</p>
                    <span className={GOAL_STATUS_BADGE[g.status]}>{GOAL_STATUS_LABEL[g.status]}</span>
                  </div>
                  <div className="mt-2">
                    <GoalProgressBar metricType={g.metric_type} currentValue={g.current_value} targetValue={g.target_value} />
                  </div>
                  {g.due_date && <p className="mt-1 text-xs text-gray-400">Due {g.due_date}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="card">
            <h2 className="mb-3 font-semibold">My pending reviews</h2>
            {myOpenReviews.length === 0 ? (
              <p className="text-sm text-gray-500">Nothing outstanding.</p>
            ) : (
              <ul className="space-y-2">
                {myOpenReviews.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-2 text-sm">
                    {r.reviewer_id === user.id ? (
                      <Link href={`/performance/reviews/${r.id}`} className="font-medium text-brand-600 hover:underline">
                        {r.type === "self" ? "Self review" : "Manager review"} · {r.cycle_name}
                      </Link>
                    ) : (
                      <span className="text-gray-600">
                        {r.type === "self" ? "Self review" : "Manager review"} · {r.cycle_name}
                      </span>
                    )}
                    <span className={REVIEW_STATUS_BADGE[r.status]}>{REVIEW_STATUS_LABEL[r.status]}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="card">
            <h2 className="mb-3 font-semibold">My upcoming 1-on-1s</h2>
            {myUpcoming.length === 0 ? (
              <p className="text-sm text-gray-500">No 1-on-1s scheduled.</p>
            ) : (
              <ul className="space-y-2">
                {myUpcoming.map((m) => (
                  <li key={m.id} className="text-sm">
                    <Link href={`/performance/one-on-ones/${m.id}`} className="font-medium text-brand-600 hover:underline">
                      With {m.other_name}
                    </Link>
                    <p className="text-xs text-gray-500">{fmtDateTime(m.scheduled_at)}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Manager section */}
      {userCanManage && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">Manager view</h2>
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="card lg:col-span-2">
              <h3 className="mb-3 font-semibold">Direct reports&apos; goals</h3>
              {reportsGoals.length === 0 ? (
                <p className="text-sm text-gray-500">Your reports have no goals yet.</p>
              ) : (
                <div className="space-y-3">
                  {reportsGoals.map((g) => (
                    <div key={g.id} className="flex flex-wrap items-center gap-3 border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                      <div className="min-w-[180px] flex-1">
                        <p className="text-sm font-medium">{g.title}</p>
                        <p className="text-xs text-gray-500">{g.employee_name}</p>
                      </div>
                      <div className="w-40">
                        <GoalProgressBar metricType={g.metric_type} currentValue={g.current_value} targetValue={g.target_value} />
                      </div>
                      <span className={GOAL_STATUS_BADGE[g.status]}>{GOAL_STATUS_LABEL[g.status]}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-6">
              <div className="card">
                <h3 className="mb-3 font-semibold">Reviews awaiting my input</h3>
                {reviewsToWrite.length === 0 ? (
                  <p className="text-sm text-gray-500">You&apos;re all caught up.</p>
                ) : (
                  <ul className="space-y-2">
                    {reviewsToWrite.map((r) => (
                      <li key={r.id} className="flex items-center justify-between gap-2 text-sm">
                        <Link href={`/performance/reviews/${r.id}`} className="font-medium text-brand-600 hover:underline">
                          {r.employee_name}
                        </Link>
                        <span className={REVIEW_STATUS_BADGE[r.status]}>{REVIEW_STATUS_LABEL[r.status]}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="card">
                <h3 className="mb-3 font-semibold">My 1-on-1s as manager</h3>
                {managerMeetings.length === 0 ? (
                  <p className="text-sm text-gray-500">No 1-on-1s scheduled with your reports.</p>
                ) : (
                  <ul className="space-y-2">
                    {managerMeetings.map((m) => (
                      <li key={m.id} className="text-sm">
                        <Link href={`/performance/one-on-ones/${m.id}`} className="font-medium text-brand-600 hover:underline">
                          With {m.other_name}
                        </Link>
                        <p className="text-xs text-gray-500">{fmtDateTime(m.scheduled_at)}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
