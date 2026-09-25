import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import LeaveTabs from "../_components/LeaveTabs";

export const dynamic = "force-dynamic";

interface ApprovedRow {
  start_date: string;
  end_date: string;
  start_half: number;
  end_half: number;
  first_name: string;
  last_name: string;
  type_name: string;
  type_colour: string;
}

function monthLabel(year: number, month: number): string {
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString("en-ZA", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function shiftMonth(year: number, month: number, delta: number): string {
  const d = new Date(Date.UTC(year, month - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export default function CalendarPage({ searchParams }: { searchParams: { month?: string } }) {
  const db = getDb();
  const user = getCurrentUser();
  const today = new Date().toISOString().slice(0, 10);

  let year: number;
  let month: number;
  if (searchParams.month && /^\d{4}-(0[1-9]|1[0-2])$/.test(searchParams.month)) {
    year = Number(searchParams.month.slice(0, 4));
    month = Number(searchParams.month.slice(5, 7));
  } else {
    year = Number(today.slice(0, 4));
    month = Number(today.slice(5, 7));
  }

  const monthStr = `${year}-${String(month).padStart(2, "0")}`;
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const firstDate = `${monthStr}-01`;
  const lastDate = `${monthStr}-${String(daysInMonth).padStart(2, "0")}`;

  const approved = db
    .prepare(
      `SELECT lr.start_date, lr.end_date, lr.start_half, lr.end_half, e.first_name, e.last_name,
              lt.name AS type_name, lt.colour AS type_colour
       FROM leave_requests lr
       JOIN employees e ON e.id = lr.employee_id
       JOIN leave_types lt ON lt.id = lr.leave_type_id
       WHERE lr.status = 'approved' AND lr.start_date <= ? AND lr.end_date >= ?
       ORDER BY e.first_name, e.last_name`
    )
    .all(lastDate, firstDate) as ApprovedRow[];

  const holidays = db
    .prepare("SELECT name, date FROM public_holidays WHERE date BETWEEN ? AND ?")
    .all(firstDate, lastDate) as { name: string; date: string }[];
  const holidayByDate = new Map(holidays.map((h) => [h.date, h.name]));

  // Build grid weeks, Monday-first.
  const firstDow = new Date(`${firstDate}T00:00:00Z`).getUTCDay(); // 0=Sun..6=Sat
  const leadingBlanks = (firstDow + 6) % 7; // days from Monday
  const cells: (number | null)[] = [
    ...Array.from({ length: leadingBlanks }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  const legendTypes = Array.from(new Map(approved.map((a) => [a.type_name, a.type_colour])).entries());

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Team Calendar</h1>
        <p className="text-sm text-gray-500">Approved leave, public holidays and weekends at a glance.</p>
      </div>

      <LeaveTabs active="calendar" showApprovals={canManage(user)} showAdmin={isHr(user)} />

      <div className="card p-0">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <Link className="btn-secondary" href={`/leave/calendar?month=${shiftMonth(year, month, -1)}`}>
            ← Prev
          </Link>
          <h2 className="font-semibold">{monthLabel(year, month)}</h2>
          <Link className="btn-secondary" href={`/leave/calendar?month=${shiftMonth(year, month, 1)}`}>
            Next →
          </Link>
        </div>

        <div className="grid grid-cols-7 border-b border-gray-200 bg-gray-50">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
            <div key={d} className="px-2 py-2 text-center text-xs font-semibold uppercase tracking-wide text-gray-500">
              {d}
            </div>
          ))}
        </div>

        {weeks.map((week, wi) => (
          <div key={wi} className="grid grid-cols-7 border-b border-gray-100 last:border-0">
            {week.map((day, di) => {
              if (day === null) {
                return <div key={di} className="min-h-[6.5rem] border-r border-gray-100 bg-gray-50/50 last:border-r-0" />;
              }
              const dateStr = `${monthStr}-${String(day).padStart(2, "0")}`;
              const isWeekend = di >= 5;
              const holiday = holidayByDate.get(dateStr);
              const onLeave = approved.filter((a) => a.start_date <= dateStr && a.end_date >= dateStr);
              const isToday = dateStr === today;
              return (
                <div
                  key={di}
                  className={`min-h-[6.5rem] border-r border-gray-100 p-1.5 last:border-r-0 ${
                    isWeekend || holiday ? "bg-gray-50" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                        isToday ? "bg-brand-600 text-white" : isWeekend || holiday ? "text-gray-400" : "text-gray-700"
                      }`}
                    >
                      {day}
                    </span>
                  </div>
                  {holiday && (
                    <p className="mt-0.5 truncate rounded bg-amber-100 px-1 py-0.5 text-[10px] font-medium text-amber-800" title={holiday}>
                      {holiday}
                    </p>
                  )}
                  <div className="mt-0.5 space-y-0.5">
                    {onLeave.map((p, i) => {
                      const isHalf =
                        (p.start_half === 1 && p.start_date === dateStr) ||
                        (p.end_half === 1 && p.end_date === dateStr);
                      return (
                        <p
                          key={i}
                          className="truncate rounded px-1 py-0.5 text-[10px] font-medium text-white"
                          style={{ backgroundColor: p.type_colour, opacity: isHalf ? 0.7 : 1 }}
                          title={`${p.first_name} ${p.last_name} — ${p.type_name}${isHalf ? " (half day)" : ""}`}
                        >
                          {isHalf && <span className="mr-0.5 font-bold">½</span>}
                          {p.first_name} {p.last_name.charAt(0)}.
                        </p>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {legendTypes.length > 0 && (
        <div className="flex flex-wrap items-center gap-4 text-xs text-gray-600">
          <span className="font-medium uppercase tracking-wide text-gray-400">Legend:</span>
          {legendTypes.map(([name, colour]) => (
            <span key={name} className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: colour }} />
              {name}
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-300" />
            Public holiday
          </span>
        </div>
      )}
    </div>
  );
}
