import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import { formatDays, getBalance } from "../_lib/leave";
import LeaveTabs from "../_components/LeaveTabs";
import DecisionButtons from "../_components/DecisionButtons";

export const dynamic = "force-dynamic";

interface ApprovalRow {
  id: number;
  employee_id: number;
  leave_type_id: number;
  start_date: string;
  end_date: string;
  days: number;
  notes: string | null;
  created_at: string;
  start_half: number;
  end_half: number;
  employee_name: string;
  job_title: string;
  type_name: string;
  type_colour: string;
}

export default function ApprovalsPage() {
  const db = getDb();
  const user = getCurrentUser();
  const year = new Date().getFullYear();

  if (!canManage(user)) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Approvals</h1>
        <LeaveTabs active="approvals" showApprovals={true} showAdmin={false} />
        <div className="card text-sm text-gray-600">
          You don&apos;t have any approval permissions. Leave approvals are handled by managers and HR.
        </div>
      </div>
    );
  }

  const rows = (
    isHr(user)
      ? db
          .prepare(
            `SELECT lr.id, lr.employee_id, lr.leave_type_id, lr.start_date, lr.end_date, lr.days, lr.notes, lr.created_at, lr.start_half, lr.end_half,
                    e.first_name || ' ' || e.last_name AS employee_name, e.job_title,
                    lt.name AS type_name, lt.colour AS type_colour
             FROM leave_requests lr
             JOIN employees e ON e.id = lr.employee_id
             JOIN leave_types lt ON lt.id = lr.leave_type_id
             WHERE lr.status = 'pending'
             ORDER BY lr.start_date, lr.id`
          )
          .all()
      : db
          .prepare(
            `SELECT lr.id, lr.employee_id, lr.leave_type_id, lr.start_date, lr.end_date, lr.days, lr.notes, lr.created_at, lr.start_half, lr.end_half,
                    e.first_name || ' ' || e.last_name AS employee_name, e.job_title,
                    lt.name AS type_name, lt.colour AS type_colour
             FROM leave_requests lr
             JOIN employees e ON e.id = lr.employee_id
             JOIN leave_types lt ON lt.id = lr.leave_type_id
             WHERE lr.status = 'pending' AND e.manager_id = ?
             ORDER BY lr.start_date, lr.id`
          )
          .all(user.id)
  ) as ApprovalRow[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Approvals</h1>
        <p className="text-sm text-gray-500">
          {isHr(user) ? "All pending leave requests." : "Pending leave requests from your direct reports."}
        </p>
      </div>

      <LeaveTabs active="approvals" showApprovals={true} showAdmin={isHr(user)} />

      {rows.length === 0 ? (
        <div className="card text-sm text-gray-500">Nothing to approve right now.</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {rows.map((r) => {
            const balance = getBalance(r.employee_id, r.leave_type_id, year)?.available ?? 0;
            return (
              <div key={r.id} className="card space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{r.employee_name}</p>
                    <p className="text-xs text-gray-500">{r.job_title}</p>
                  </div>
                  <span
                    className="badge text-white"
                    style={{ backgroundColor: r.type_colour }}
                  >
                    {r.type_name}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <p className="label">Dates</p>
                    <p className="whitespace-nowrap">
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
                    </p>
                  </div>
                  <div>
                    <p className="label">Working days</p>
                    <p>{formatDays(r.days)}</p>
                  </div>
                  <div>
                    <p className="label">Current balance</p>
                    <p className={balance < r.days ? "font-medium text-red-600" : ""}>{formatDays(balance)} days</p>
                  </div>
                </div>
                {r.notes && <p className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600">&ldquo;{r.notes}&rdquo;</p>}
                <DecisionButtons requestId={r.id} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
