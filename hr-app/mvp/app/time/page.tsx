import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, canManage } from "@/lib/session";
import type { ClockEvent, Timesheet } from "@/lib/types";
import ClockWidget from "./_components/ClockWidget";
import SubmitTimesheetButton from "./_components/SubmitTimesheetButton";
import AddTimeEntryForm from "./_components/AddTimeEntryForm";
import {
  EVENT_LABELS,
  STANDARD_WEEK_MINUTES,
  addDays,
  clockStateFromEvents,
  fmtMinutes,
  fmtTime,
  isValidDateString,
  mondayOf,
  nowSql,
  todaySql,
  workedMinutes,
} from "./_lib/time";

export const dynamic = "force-dynamic";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const STATUS_BADGES: Record<Timesheet["status"], { className: string; label: string }> = {
  draft: { className: "badge-gray", label: "Draft" },
  submitted: { className: "badge-blue", label: "Submitted" },
  approved: { className: "badge-green", label: "Approved" },
  rejected: { className: "badge-red", label: "Rejected" },
};

export default function TimePage({ searchParams }: { searchParams: { week?: string } }) {
  const db = getDb();
  const user = getCurrentUser();
  const today = todaySql();
  const now = nowSql();
  const currentMonday = mondayOf(today);

  const weekStart = isValidDateString(searchParams.week) ? mondayOf(searchParams.week) : currentMonday;
  const weekEnd = addDays(weekStart, 6);

  // Today's events + clock state
  const todayEvents = db
    .prepare(
      "SELECT * FROM clock_events WHERE employee_id = ? AND date(timestamp) = ? ORDER BY timestamp, id"
    )
    .all(user.id, today) as ClockEvent[];
  const state = clockStateFromEvents(todayEvents);
  const sinceEvent =
    state === "in"
      ? [...todayEvents].reverse().find((e) => e.type === "clock_in")
      : state === "on_break"
        ? [...todayEvents].reverse().find((e) => e.type === "break_start")
        : undefined;

  // Displayed week's events, grouped per day
  const weekEvents = db
    .prepare(
      `SELECT * FROM clock_events
       WHERE employee_id = ? AND date(timestamp) BETWEEN ? AND ?
       ORDER BY timestamp, id`
    )
    .all(user.id, weekStart, weekEnd) as ClockEvent[];

  const days = Array.from({ length: 7 }, (_, i) => {
    const date = addDays(weekStart, i);
    const events = weekEvents.filter((e) => e.timestamp.slice(0, 10) === date);
    const minutes = workedMinutes(events, date === today ? now : undefined);
    return { date, name: DAY_NAMES[i], minutes };
  });
  const weekTotal = days.reduce((sum, d) => sum + d.minutes, 0);
  const overtime = Math.max(0, weekTotal - STANDARD_WEEK_MINUTES);
  const maxDay = Math.max(600, ...days.map((d) => d.minutes)); // bar scale: at least 10h

  // Timesheet for the displayed week + my past timesheets
  const weekTimesheet = db
    .prepare("SELECT * FROM timesheets WHERE employee_id = ? AND period_start = ?")
    .get(user.id, weekStart) as Timesheet | undefined;
  const canSubmit =
    weekStart <= currentMonday &&
    (!weekTimesheet || weekTimesheet.status === "draft" || weekTimesheet.status === "rejected");

  const myTimesheets = db
    .prepare("SELECT * FROM timesheets WHERE employee_id = ? ORDER BY period_start DESC")
    .all(user.id) as Timesheet[];

  const myEntries = db
    .prepare("SELECT * FROM manual_time_entries WHERE employee_id = ? ORDER BY date DESC, id DESC LIMIT 20")
    .all(user.id) as {
    id: number;
    date: string;
    start_time: string;
    end_time: string;
    break_minutes: number;
    reason: string;
    status: "pending" | "approved" | "rejected";
    decided_at: string | null;
  }[];

  const ENTRY_BADGES = {
    pending: "badge-yellow",
    approved: "badge-green",
    rejected: "badge-red",
  } as const;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Time &amp; Attendance</h1>
          <p className="text-sm text-gray-500">Clock your hours and submit weekly timesheets.</p>
        </div>
        {canManage(user) && (
          <Link href="/time/team" className="btn-secondary">
            Team view →
          </Link>
        )}
      </div>

      <div className="card">
        <ClockWidget state={state} sinceTime={sinceEvent ? fmtTime(sinceEvent.timestamp) : null} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card">
          <h2 className="mb-3 font-semibold">Today&apos;s events</h2>
          {todayEvents.length === 0 ? (
            <p className="text-sm text-gray-500">No clock events yet today.</p>
          ) : (
            <ul className="space-y-2">
              {todayEvents.map((e) => (
                <li key={e.id} className="flex items-center justify-between text-sm">
                  <span>{EVENT_LABELS[e.type]}</span>
                  <span className="font-mono text-gray-500">{fmtTime(e.timestamp)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">
              Week of {weekStart} – {weekEnd}
              {weekStart === currentMonday && <span className="ml-2 badge-blue">Current</span>}
            </h2>
            <div className="flex items-center gap-2 text-sm">
              <Link href={`/time?week=${addDays(weekStart, -7)}`} className="btn-secondary">
                ← Prev
              </Link>
              <Link href={`/time?week=${addDays(weekStart, 7)}`} className="btn-secondary">
                Next →
              </Link>
            </div>
          </div>

          <div className="space-y-1.5">
            {days.map((d) => (
              <div key={d.date} className="flex items-center gap-3 text-sm">
                <span className={`w-10 shrink-0 ${d.date === today ? "font-semibold" : "text-gray-500"}`}>
                  {d.name}
                </span>
                <div className="h-4 flex-1 overflow-hidden rounded bg-gray-100">
                  <div
                    className="h-full rounded bg-brand-600"
                    style={{ width: `${Math.min(100, (d.minutes / maxDay) * 100)}%` }}
                  />
                </div>
                <span className="w-20 shrink-0 text-right font-mono text-gray-600">
                  {d.minutes > 0 ? fmtMinutes(d.minutes) : "—"}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-4">
            <div className="flex items-center gap-4 text-sm">
              <span>
                Total: <span className="font-semibold">{fmtMinutes(weekTotal)}</span>
              </span>
              <span>
                Overtime:{" "}
                {overtime > 0 ? (
                  <span className="badge-yellow">{fmtMinutes(overtime)}</span>
                ) : (
                  <span className="text-gray-500">none</span>
                )}
              </span>
              {weekTimesheet && (
                <span className={STATUS_BADGES[weekTimesheet.status].className}>
                  {STATUS_BADGES[weekTimesheet.status].label}
                </span>
              )}
            </div>
            {canSubmit ? (
              <SubmitTimesheetButton
                periodStart={weekStart}
                label={weekTimesheet?.status === "rejected" ? "Resubmit timesheet" : "Submit timesheet"}
              />
            ) : weekStart > currentMonday ? (
              <p className="text-sm text-gray-400">Future weeks cannot be submitted.</p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Timesheet corrections</h2>
        </div>
        <div className="mb-4">
          <AddTimeEntryForm minDate={addDays(today, -14)} maxDate={today} />
        </div>
        {myEntries.length === 0 ? (
          <p className="text-sm text-gray-500">
            No corrections yet. Use &ldquo;Add missing time&rdquo; if you forgot to clock in or out.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="th">Date</th>
                  <th className="th">Time</th>
                  <th className="th">Break</th>
                  <th className="th">Reason</th>
                  <th className="th">Status</th>
                </tr>
              </thead>
              <tbody>
                {myEntries.map((m) => (
                  <tr key={m.id} className="border-b border-gray-100 last:border-0">
                    <td className="td whitespace-nowrap">{m.date}</td>
                    <td className="td font-mono">
                      {m.start_time}–{m.end_time}
                    </td>
                    <td className="td">{m.break_minutes > 0 ? `${m.break_minutes} min` : "—"}</td>
                    <td className="td max-w-xs truncate" title={m.reason}>{m.reason}</td>
                    <td className="td">
                      <span className={`${ENTRY_BADGES[m.status]} capitalize`}>{m.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">My timesheets</h2>
        {myTimesheets.length === 0 ? (
          <p className="text-sm text-gray-500">No timesheets submitted yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="th">Week</th>
                  <th className="th">Total</th>
                  <th className="th">Overtime</th>
                  <th className="th">Status</th>
                  <th className="th">Submitted</th>
                  <th className="th">Decided</th>
                </tr>
              </thead>
              <tbody>
                {myTimesheets.map((t) => (
                  <tr key={t.id} className="border-b border-gray-100 last:border-0">
                    <td className="td">
                      <Link href={`/time?week=${t.period_start}`} className="font-medium text-brand-600 hover:underline">
                        {t.period_start} – {t.period_end}
                      </Link>
                    </td>
                    <td className="td font-mono">{fmtMinutes(t.total_minutes)}</td>
                    <td className="td font-mono">{t.overtime_minutes > 0 ? fmtMinutes(t.overtime_minutes) : "—"}</td>
                    <td className="td">
                      <span className={STATUS_BADGES[t.status].className}>{STATUS_BADGES[t.status].label}</span>
                    </td>
                    <td className="td text-gray-500">{t.submitted_at?.slice(0, 16) ?? "—"}</td>
                    <td className="td text-gray-500">{t.decided_at?.slice(0, 16) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
