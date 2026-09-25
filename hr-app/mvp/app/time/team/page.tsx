import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import type { ClockEvent, Employee, Timesheet } from "@/lib/types";
import TimesheetActions from "../_components/TimesheetActions";
import TimeEntryActions from "../_components/TimeEntryActions";
import {
  clockStateFromEvents,
  fmtMinutes,
  fmtTime,
  nowSql,
  todaySql,
  workedMinutes,
  type ClockState,
} from "../_lib/time";

export const dynamic = "force-dynamic";

const STATE_BADGES: Record<ClockState, { className: string; label: string }> = {
  in: { className: "badge-green", label: "Clocked in" },
  on_break: { className: "badge-yellow", label: "On break" },
  out: { className: "badge-gray", label: "Out" },
};

export default function TeamTimePage() {
  const db = getDb();
  const user = getCurrentUser();

  if (!canManage(user)) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Team attendance</h1>
        <div className="card">
          <p className="text-sm text-gray-600">
            This page is only available to managers and HR. Looking for your own hours?{" "}
            <Link href="/time" className="font-medium text-brand-600 hover:underline">
              Go to My Time →
            </Link>
          </p>
        </div>
      </div>
    );
  }

  const today = todaySql();
  const now = nowSql();
  const hr = isHr(user);

  const team = (
    hr
      ? db.prepare(
          "SELECT * FROM employees WHERE status = 'active' ORDER BY first_name, last_name"
        ).all()
      : db.prepare(
          "SELECT * FROM employees WHERE status = 'active' AND manager_id = ? ORDER BY first_name, last_name"
        ).all(user.id)
  ) as Employee[];

  const eventsByEmployee = new Map<number, ClockEvent[]>();
  if (team.length > 0) {
    const placeholders = team.map(() => "?").join(",");
    const todayEvents = db
      .prepare(
        `SELECT * FROM clock_events
         WHERE date(timestamp) = ? AND employee_id IN (${placeholders})
         ORDER BY timestamp, id`
      )
      .all(today, ...team.map((e) => e.id)) as ClockEvent[];
    for (const e of todayEvents) {
      const list = eventsByEmployee.get(e.employee_id) ?? [];
      list.push(e);
      eventsByEmployee.set(e.employee_id, list);
    }
  }

  const board = team.map((emp) => {
    const events = eventsByEmployee.get(emp.id) ?? [];
    const state = clockStateFromEvents(events);
    const firstIn = events.find((e) => e.type === "clock_in");
    const lastOut = [...events].reverse().find((e) => e.type === "clock_out");
    return {
      emp,
      state,
      firstIn: firstIn ? fmtTime(firstIn.timestamp) : null,
      lastOut: lastOut ? fmtTime(lastOut.timestamp) : null,
      workedSoFar: workedMinutes(events, now),
    };
  });

  const pending = (
    hr
      ? db.prepare(
          `SELECT t.*, e.first_name || ' ' || e.last_name AS employee_name, e.job_title
           FROM timesheets t JOIN employees e ON e.id = t.employee_id
           WHERE t.status = 'submitted' ORDER BY t.period_start, employee_name`
        ).all()
      : db.prepare(
          `SELECT t.*, e.first_name || ' ' || e.last_name AS employee_name, e.job_title
           FROM timesheets t JOIN employees e ON e.id = t.employee_id
           WHERE t.status = 'submitted' AND e.manager_id = ? ORDER BY t.period_start, employee_name`
        ).all(user.id)
  ) as (Timesheet & { employee_name: string; job_title: string })[];

  const pendingEntries = (
    hr
      ? db.prepare(
          `SELECT m.*, e.first_name || ' ' || e.last_name AS employee_name, e.job_title
           FROM manual_time_entries m JOIN employees e ON e.id = m.employee_id
           WHERE m.status = 'pending' ORDER BY m.date, m.id`
        ).all()
      : db.prepare(
          `SELECT m.*, e.first_name || ' ' || e.last_name AS employee_name, e.job_title
           FROM manual_time_entries m JOIN employees e ON e.id = m.employee_id
           WHERE m.status = 'pending' AND e.manager_id = ? ORDER BY m.date, m.id`
        ).all(user.id)
  ) as {
    id: number;
    date: string;
    start_time: string;
    end_time: string;
    break_minutes: number;
    reason: string;
    created_at: string;
    employee_name: string;
    job_title: string;
  }[];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Team attendance</h1>
          <p className="text-sm text-gray-500">
            {hr ? "All active employees" : "Your direct reports"} · today, {today}
          </p>
        </div>
        <Link href="/time" className="btn-secondary">
          ← My time
        </Link>
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Today&apos;s attendance board</h2>
        {board.length === 0 ? (
          <p className="text-sm text-gray-500">No employees to show.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="th">Employee</th>
                  <th className="th">Status</th>
                  <th className="th">First in</th>
                  <th className="th">Last out</th>
                  <th className="th">Worked so far</th>
                </tr>
              </thead>
              <tbody>
                {board.map(({ emp, state, firstIn, lastOut, workedSoFar }) => (
                  <tr key={emp.id} className="border-b border-gray-100 last:border-0">
                    <td className="td">
                      <p className="font-medium text-gray-900">
                        {emp.first_name} {emp.last_name}
                      </p>
                      <p className="text-xs text-gray-500">{emp.job_title}</p>
                    </td>
                    <td className="td">
                      <span className={STATE_BADGES[state].className}>{STATE_BADGES[state].label}</span>
                    </td>
                    <td className="td font-mono">{firstIn ?? "—"}</td>
                    <td className="td font-mono">{lastOut ?? "—"}</td>
                    <td className="td font-mono">{workedSoFar > 0 ? fmtMinutes(workedSoFar) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Pending timesheet corrections</h2>
        {pendingEntries.length === 0 ? (
          <p className="text-sm text-gray-500">No corrections waiting for review.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="th">Employee</th>
                  <th className="th">Date</th>
                  <th className="th">Time</th>
                  <th className="th">Break</th>
                  <th className="th">Reason</th>
                  <th className="th text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingEntries.map((m) => (
                  <tr key={m.id} className="border-b border-gray-100 last:border-0">
                    <td className="td">
                      <p className="font-medium text-gray-900">{m.employee_name}</p>
                      <p className="text-xs text-gray-500">{m.job_title}</p>
                    </td>
                    <td className="td whitespace-nowrap">{m.date}</td>
                    <td className="td font-mono">
                      {m.start_time}–{m.end_time}
                    </td>
                    <td className="td">{m.break_minutes > 0 ? `${m.break_minutes} min` : "—"}</td>
                    <td className="td max-w-xs">
                      <span className="block truncate" title={m.reason}>{m.reason}</span>
                    </td>
                    <td className="td">
                      <div className="flex justify-end">
                        <TimeEntryActions entryId={m.id} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Pending timesheets</h2>
        {pending.length === 0 ? (
          <p className="text-sm text-gray-500">No timesheets waiting for review.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="th">Employee</th>
                  <th className="th">Week</th>
                  <th className="th">Total</th>
                  <th className="th">Overtime</th>
                  <th className="th">Submitted</th>
                  <th className="th text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((t) => (
                  <tr key={t.id} className="border-b border-gray-100 last:border-0">
                    <td className="td">
                      <p className="font-medium text-gray-900">{t.employee_name}</p>
                      <p className="text-xs text-gray-500">{t.job_title}</p>
                    </td>
                    <td className="td">
                      {t.period_start} – {t.period_end}
                    </td>
                    <td className="td font-mono">{fmtMinutes(t.total_minutes)}</td>
                    <td className="td">
                      {t.overtime_minutes > 0 ? (
                        <span className="badge-yellow">{fmtMinutes(t.overtime_minutes)}</span>
                      ) : (
                        <span className="text-gray-500">—</span>
                      )}
                    </td>
                    <td className="td text-gray-500">{t.submitted_at?.slice(0, 16) ?? "—"}</td>
                    <td className="td">
                      <div className="flex justify-end">
                        <TimesheetActions timesheetId={t.id} />
                      </div>
                    </td>
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
