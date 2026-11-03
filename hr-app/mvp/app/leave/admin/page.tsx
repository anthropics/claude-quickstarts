import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import type { LeaveType } from "@/lib/types";
import { formatDays } from "../_lib/leave";
import LeaveTabs from "../_components/LeaveTabs";
import LeaveTypeForm from "../_components/LeaveTypeForm";

export const dynamic = "force-dynamic";

export default function LeaveAdminPage() {
  const db = getDb();
  const user = getCurrentUser();
  const year = new Date().getFullYear();

  if (!isHr(user)) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Leave Admin</h1>
        <LeaveTabs active="admin" showApprovals={canManage(user)} showAdmin={false} />
        <div className="card text-sm text-gray-600">
          This area is restricted to HR and admins. Please contact People &amp; Culture if you need a change to leave
          policies.
        </div>
      </div>
    );
  }

  const leaveTypes = db.prepare("SELECT * FROM leave_types ORDER BY id").all() as LeaveType[];
  const holidays = db
    .prepare("SELECT name, date, region FROM public_holidays WHERE strftime('%Y', date) = ? ORDER BY date")
    .all(String(year)) as { name: string; date: string; region: string }[];

  const yesNo = (v: number) =>
    v === 1 ? <span className="badge-green">Yes</span> : <span className="badge-gray">No</span>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Leave Admin</h1>
        <p className="text-sm text-gray-500">Manage leave types and review the public holiday calendar.</p>
      </div>

      <LeaveTabs active="admin" showApprovals={canManage(user)} showAdmin={true} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="th">Name</th>
                  <th className="th">Code</th>
                  <th className="th">Entitlement</th>
                  <th className="th">Paid</th>
                  <th className="th">Probation restricted</th>
                  <th className="th">Negative allowed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {leaveTypes.map((lt) => (
                  <tr key={lt.id}>
                    <td className="td">
                      <span className="inline-flex items-center gap-2 font-medium text-gray-900">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: lt.colour }} />
                        {lt.name}
                      </span>
                    </td>
                    <td className="td font-mono text-xs">{lt.code}</td>
                    <td className="td">{formatDays(lt.annual_entitlement_days)} days</td>
                    <td className="td">{yesNo(lt.paid)}</td>
                    <td className="td">{yesNo(lt.probation_restricted)}</td>
                    <td className="td">{yesNo(lt.negative_balance_allowed)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2 className="mb-3 font-semibold">Add leave type</h2>
            <LeaveTypeForm />
          </div>
        </div>

        <div className="card self-start">
          <h2 className="mb-3 font-semibold">Public holidays {year}</h2>
          {holidays.length === 0 ? (
            <p className="text-sm text-gray-500">No public holidays configured for {year}.</p>
          ) : (
            <ul className="space-y-2">
              {holidays.map((h, i) => (
                <li key={i} className="flex items-center justify-between text-sm">
                  <span>{h.name}</span>
                  <span className="whitespace-nowrap text-gray-500">{h.date}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
