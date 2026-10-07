import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import type { LeaveType } from "@/lib/types";
import { formatDays, getBalances, statusBadgeClass } from "./_lib/leave";
import LeaveTabs from "./_components/LeaveTabs";
import RequestForm from "./_components/RequestForm";
import CancelButton from "./_components/CancelButton";

export const dynamic = "force-dynamic";

interface MyRequestRow {
  id: number;
  start_date: string;
  end_date: string;
  days: number;
  notes: string | null;
  status: string;
  decision_note: string | null;
  start_half: number;
  end_half: number;
  type_name: string;
  type_colour: string;
}

export default function MyLeavePage() {
  const db = getDb();
  const user = getCurrentUser();
  const year = new Date().getFullYear();

  const balances = getBalances(user.id, year);
  const leaveTypes = db.prepare("SELECT id, name, colour FROM leave_types ORDER BY id").all() as Pick<
    LeaveType,
    "id" | "name" | "colour"
  >[];

  const requests = db
    .prepare(
      `SELECT lr.id, lr.start_date, lr.end_date, lr.days, lr.notes, lr.status, lr.decision_note,
              lr.start_half, lr.end_half,
              lt.name AS type_name, lt.colour AS type_colour
       FROM leave_requests lr
       JOIN leave_types lt ON lt.id = lr.leave_type_id
       WHERE lr.employee_id = ?
       ORDER BY lr.start_date DESC, lr.id DESC`
    )
    .all(user.id) as MyRequestRow[];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Leave</h1>
          <p className="text-sm text-gray-500">Your balances and requests for {year}.</p>
        </div>
      </div>

      <LeaveTabs active="my" showApprovals={canManage(user)} showAdmin={isHr(user)} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {balances.map((b) => (
          <div key={b.leaveType.id} className="card border-l-4 p-4" style={{ borderLeftColor: b.leaveType.colour }}>
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{b.leaveType.name}</p>
            <p className="mt-1 text-2xl font-bold">
              {formatDays(b.available)} <span className="text-sm font-normal text-gray-400">available</span>
            </p>
            <p className="mt-1 text-xs text-gray-500">
              {formatDays(b.entitled)} entitled
              {b.leaveType.accrual_method === "monthly" && <span className="text-gray-400"> (accrued to date)</span>}
              {" · "}{formatDays(b.taken)} taken
              {b.pending > 0 && <span className="text-yellow-700"> · {formatDays(b.pending)} pending</span>}
            </p>
            {b.carryOver > 0 && (
              <p className="mt-0.5 text-xs font-medium text-brand-700">
                +{formatDays(b.carryOver)} carried over, expires year-end
              </p>
            )}
          </div>
        ))}
      </div>

      <RequestForm leaveTypes={leaveTypes} />

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Type</th>
              <th className="th">Dates</th>
              <th className="th">Days</th>
              <th className="th">Status</th>
              <th className="th">Notes</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {requests.length === 0 && (
              <tr>
                <td className="td text-gray-500" colSpan={6}>
                  No leave requests yet.
                </td>
              </tr>
            )}
            {requests.map((r) => (
              <tr key={r.id}>
                <td className="td">
                  <span className="inline-flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: r.type_colour }} />
                    {r.type_name}
                  </span>
                </td>
                <td className="td whitespace-nowrap">
                  {r.start_date}
                  {r.start_half === 1 && (
                    <span className="ml-0.5 font-semibold text-brand-600" title={r.end_date === r.start_date ? "Half day" : "First day is a half day (afternoon)"}>½</span>
                  )}
                  {r.end_date !== r.start_date && (
                    <>
                      {" "}→ {r.end_date}
                      {r.end_half === 1 && (
                        <span className="ml-0.5 font-semibold text-brand-600" title="Last day is a half day (morning)">½</span>
                      )}
                    </>
                  )}
                </td>
                <td className="td">{formatDays(r.days)}</td>
                <td className="td">
                  <span className={`${statusBadgeClass(r.status)} capitalize`}>{r.status}</span>
                </td>
                <td className="td max-w-xs">
                  {r.notes ?? <span className="text-gray-400">—</span>}
                  {r.decision_note && <p className="text-xs text-gray-400">Decision: {r.decision_note}</p>}
                </td>
                <td className="td text-right">{r.status === "pending" && <CancelButton requestId={r.id} />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
