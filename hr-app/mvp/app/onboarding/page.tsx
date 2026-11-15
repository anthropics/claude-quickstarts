import Link from "next/link";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import StartOnboardingModal from "./_components/StartOnboardingModal";

export const dynamic = "force-dynamic";

interface InstanceRow {
  id: number;
  employee_id: number;
  template_id: number;
  created_at: string;
  completed_at: string | null;
  employee_name: string;
  start_date: string;
  template_name: string;
  total_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
}

function statusBadge(row: InstanceRow) {
  if (row.completed_at) return <span className="badge-green">Completed</span>;
  if (row.overdue_tasks > 0) return <span className="badge-red">Overdue</span>;
  return <span className="badge-blue">On Track</span>;
}

const INSTANCES_SQL = `
  SELECT oi.id, oi.employee_id, oi.template_id, oi.created_at, oi.completed_at,
         e.first_name || ' ' || e.last_name AS employee_name,
         e.start_date,
         ot.name AS template_name,
         COUNT(t.id) AS total_tasks,
         SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) AS completed_tasks,
         SUM(CASE WHEN t.status NOT IN ('completed','skipped') AND t.due_date < date('now') THEN 1 ELSE 0 END) AS overdue_tasks
  FROM onboarding_instances oi
  JOIN employees e ON e.id = oi.employee_id
  JOIN onboarding_templates ot ON ot.id = oi.template_id
  LEFT JOIN onboarding_tasks t ON t.instance_id = oi.id
  WHERE {WHERE}
  GROUP BY oi.id
  ORDER BY oi.created_at DESC
`;

export default function OnboardingPage() {
  const db = getDb();
  const user = getCurrentUser();
  const userIsHr = isHr(user);
  const userCanManage = canManage(user);

  // Employees redirect to their own onboarding
  if (!userCanManage) {
    redirect("/onboarding/me");
  }

  // Build instance rows
  let instances: InstanceRow[];
  if (userIsHr) {
    instances = db.prepare(INSTANCES_SQL.replace("{WHERE}", "1=1")).all() as InstanceRow[];
  } else {
    // Manager: only direct reports
    instances = db
      .prepare(INSTANCES_SQL.replace("{WHERE}", "e.manager_id = ?"))
      .all(user.id) as InstanceRow[];
  }

  // Summary stats (HR only)
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    .toISOString()
    .slice(0, 10);

  const activeCount = instances.filter((i) => !i.completed_at).length;
  const overdueTasksCount = userIsHr
    ? (
        db
          .prepare(
            "SELECT COUNT(*) AS n FROM onboarding_tasks WHERE status NOT IN ('completed','skipped') AND due_date < ?"
          )
          .get(today) as { n: number }
      ).n
    : instances.reduce((sum, i) => sum + (i.overdue_tasks ?? 0), 0);
  const completedThisMonth = instances.filter(
    (i) => i.completed_at && i.completed_at.slice(0, 10) >= firstOfMonth
  ).length;

  // Data for the modal
  const employees = userIsHr
    ? (db
        .prepare("SELECT id, first_name, last_name FROM employees WHERE status = 'active' ORDER BY first_name")
        .all() as { id: number; first_name: string; last_name: string }[])
    : [];
  const templates = userIsHr
    ? (db
        .prepare("SELECT id, name FROM onboarding_templates ORDER BY name")
        .all() as { id: number; name: string }[])
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Onboarding</h1>
          <p className="text-sm text-gray-500">
            {userIsHr ? "Manage all employee onboarding journeys." : "Onboarding for your direct reports."}
          </p>
        </div>
        <div className="flex gap-2">
          {userIsHr && (
            <>
              <Link href="/onboarding/templates" className="btn-secondary text-sm">
                Templates
              </Link>
              <StartOnboardingModal employees={employees} templates={templates} />
            </>
          )}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Active onboardings</p>
          <p className="mt-1 text-3xl font-bold">{activeCount}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Tasks overdue</p>
          <p className="mt-1 text-3xl font-bold text-red-600">{overdueTasksCount}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Completed this month</p>
          <p className="mt-1 text-3xl font-bold text-green-600">{completedThisMonth}</p>
        </div>
      </div>

      {/* Instances table */}
      <div className="card overflow-x-auto p-0">
        <div className="border-b border-gray-100 px-5 py-3">
          <h2 className="font-semibold">Onboarding Journeys</h2>
        </div>
        <table className="w-full min-w-[700px]">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Employee</th>
              <th className="th">Start Date</th>
              <th className="th">Template</th>
              <th className="th">Progress</th>
              <th className="th">Status</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {instances.length === 0 && (
              <tr>
                <td className="td py-8 text-center text-gray-500" colSpan={6}>
                  No onboarding journeys yet.
                </td>
              </tr>
            )}
            {instances.map((inst) => {
              const pct = inst.total_tasks > 0
                ? Math.round((inst.completed_tasks / inst.total_tasks) * 100)
                : 0;
              return (
                <tr key={inst.id} className="hover:bg-gray-50">
                  <td className="td font-medium">{inst.employee_name}</td>
                  <td className="td">{inst.start_date}</td>
                  <td className="td">{inst.template_name}</td>
                  <td className="td min-w-[160px]">
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 rounded-full bg-gray-200">
                        <div
                          className="h-2 rounded-full bg-brand-600"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">
                        {inst.completed_tasks}/{inst.total_tasks}
                      </span>
                    </div>
                  </td>
                  <td className="td">{statusBadge(inst)}</td>
                  <td className="td text-right">
                    <Link
                      href={`/onboarding/${inst.id}`}
                      className="text-sm text-brand-600 hover:underline"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
