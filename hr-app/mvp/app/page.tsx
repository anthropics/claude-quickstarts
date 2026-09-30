import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, canManage } from "@/lib/session";

export const dynamic = "force-dynamic";

export default function Dashboard() {
  const db = getDb();
  const user = getCurrentUser();
  const today = new Date().toISOString().slice(0, 10);
  const year = today.slice(0, 4);

  const headcount = (db.prepare("SELECT COUNT(*) AS n FROM employees WHERE status = 'active'").get() as { n: number }).n;

  const annual = db
    .prepare(
      `SELECT lt.annual_entitlement_days - COALESCE(SUM(CASE WHEN lr.status = 'approved' THEN lr.days ELSE 0 END), 0) AS balance
       FROM leave_types lt
       LEFT JOIN leave_requests lr
         ON lr.leave_type_id = lt.id AND lr.employee_id = ? AND lr.start_date >= ?
       WHERE lt.code = 'ANNUAL'
       GROUP BY lt.id`
    )
    .get(user.id, `${year}-01-01`) as { balance: number } | undefined;

  const lastClock = db
    .prepare("SELECT type FROM clock_events WHERE employee_id = ? AND date(timestamp) = ? ORDER BY timestamp DESC LIMIT 1")
    .get(user.id, today) as { type: string } | undefined;
  const clockedIn = lastClock?.type === "clock_in" || lastClock?.type === "break_end";

  const pendingApprovals = canManage(user)
    ? (
        db
          .prepare(
            `SELECT COUNT(*) AS n FROM leave_requests lr
             JOIN employees e ON e.id = lr.employee_id
             WHERE lr.status = 'pending' AND (e.manager_id = ? OR ? IN ('hr', 'admin'))`
          )
          .get(user.id, user.role) as { n: number }
      ).n
    : 0;

  const onLeaveToday = db
    .prepare(
      `SELECT e.first_name || ' ' || e.last_name AS name, lt.name AS leave_type, lr.end_date
       FROM leave_requests lr
       JOIN employees e ON e.id = lr.employee_id
       JOIN leave_types lt ON lt.id = lr.leave_type_id
       WHERE lr.status = 'approved' AND lr.start_date <= ? AND lr.end_date >= ?`
    )
    .all(today, today) as { name: string; leave_type: string; end_date: string }[];

  const announcements = db
    .prepare(
      `SELECT a.title, a.body, a.created_at, e.first_name || ' ' || e.last_name AS author
       FROM announcements a LEFT JOIN employees e ON e.id = a.author_id
       ORDER BY a.created_at DESC LIMIT 5`
    )
    .all() as { title: string; body: string; created_at: string; author: string | null }[];

  const upcomingHolidays = db
    .prepare("SELECT name, date FROM public_holidays WHERE date >= ? ORDER BY date LIMIT 3")
    .all(today) as { name: string; date: string }[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Welcome back, {user.first_name}</h1>
        <p className="text-sm text-gray-500">Here&apos;s what&apos;s happening at Acme today.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Annual leave balance</p>
          <p className="mt-1 text-3xl font-bold">{annual ? annual.balance : "—"} <span className="text-base font-normal text-gray-400">days</span></p>
          <Link href="/leave" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">Request leave →</Link>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Clock status</p>
          <p className="mt-1 text-3xl font-bold">{clockedIn ? "In" : "Out"}</p>
          <Link href="/time" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">
            {clockedIn ? "Clock out →" : "Clock in →"}
          </Link>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Active employees</p>
          <p className="mt-1 text-3xl font-bold">{headcount}</p>
          <Link href="/employees" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">View directory →</Link>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Pending approvals</p>
          <p className="mt-1 text-3xl font-bold">{pendingApprovals}</p>
          {canManage(user) && (
            <Link href="/leave/approvals" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">Review →</Link>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card lg:col-span-2">
          <h2 className="mb-3 font-semibold">Announcements</h2>
          <div className="space-y-4">
            {announcements.length === 0 && <p className="text-sm text-gray-500">No announcements yet.</p>}
            {announcements.map((a, i) => (
              <div key={i} className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                <p className="font-medium">{a.title}</p>
                <p className="text-sm text-gray-600">{a.body}</p>
                <p className="mt-1 text-xs text-gray-400">
                  {a.author ?? "System"} · {a.created_at.slice(0, 10)}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="card">
            <h2 className="mb-3 font-semibold">Who&apos;s out today</h2>
            {onLeaveToday.length === 0 ? (
              <p className="text-sm text-gray-500">Everyone is in today.</p>
            ) : (
              <ul className="space-y-2">
                {onLeaveToday.map((p, i) => (
                  <li key={i} className="flex items-center justify-between text-sm">
                    <span>{p.name}</span>
                    <span className="badge-gray">{p.leave_type}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="card">
            <h2 className="mb-3 font-semibold">Upcoming public holidays</h2>
            <ul className="space-y-2">
              {upcomingHolidays.map((h, i) => (
                <li key={i} className="flex items-center justify-between text-sm">
                  <span>{h.name}</span>
                  <span className="text-gray-500">{h.date}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
