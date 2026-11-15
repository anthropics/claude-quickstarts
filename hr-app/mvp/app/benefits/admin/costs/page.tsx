import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import BenefitsTabs from "../../_components/BenefitsTabs";
import { categoryBadgeClass, categoryLabel, fmtRand } from "../../_lib/benefits";

export const dynamic = "force-dynamic";

interface CategoryRow {
  category: string;
  employee_total: number;
  employer_total: number;
}

interface EmployeeRow {
  employee_id: number;
  employee_name: string;
  department_name: string | null;
  employee_total: number;
  employer_total: number;
  benefit_count: number;
}

interface PlanRow {
  plan_id: number;
  plan_name: string;
  category: string;
  enrolled_count: number;
  employer_total: number;
  employee_total: number;
}

export default function CostReportPage() {
  const db = getDb();
  const user = getCurrentUser();
  if (!isHr(user)) redirect("/benefits");

  const totals = db
    .prepare(
      `SELECT COALESCE(SUM(bt.monthly_cost_employee), 0) AS employee_total,
              COALESCE(SUM(bt.monthly_cost_employer), 0) AS employer_total
       FROM benefit_elections be
       JOIN benefit_tiers bt ON bt.id = be.tier_id
       WHERE be.status = 'active'`
    )
    .get() as { employee_total: number; employer_total: number };

  const byCategory = db
    .prepare(
      `SELECT bp.category,
              SUM(bt.monthly_cost_employee) AS employee_total,
              SUM(bt.monthly_cost_employer) AS employer_total
       FROM benefit_elections be
       JOIN benefit_tiers bt ON bt.id = be.tier_id
       JOIN benefit_plans bp ON bp.id = bt.plan_id
       WHERE be.status = 'active'
       GROUP BY bp.category
       ORDER BY employer_total DESC`
    )
    .all() as CategoryRow[];

  const byEmployee = db
    .prepare(
      `SELECT e.id AS employee_id,
              e.first_name || ' ' || e.last_name AS employee_name,
              d.name AS department_name,
              SUM(bt.monthly_cost_employee) AS employee_total,
              SUM(bt.monthly_cost_employer) AS employer_total,
              COUNT(*) AS benefit_count
       FROM benefit_elections be
       JOIN employees e ON e.id = be.employee_id
       JOIN benefit_tiers bt ON bt.id = be.tier_id
       LEFT JOIN departments d ON d.id = e.department_id
       WHERE be.status = 'active'
       GROUP BY e.id
       ORDER BY employer_total DESC, employee_name`
    )
    .all() as EmployeeRow[];

  const byPlan = db
    .prepare(
      `SELECT bp.id AS plan_id, bp.name AS plan_name, bp.category,
              COUNT(*) AS enrolled_count,
              SUM(bt.monthly_cost_employer) AS employer_total,
              SUM(bt.monthly_cost_employee) AS employee_total
       FROM benefit_elections be
       JOIN benefit_tiers bt ON bt.id = be.tier_id
       JOIN benefit_plans bp ON bp.id = bt.plan_id
       WHERE be.status = 'active'
       GROUP BY bp.id
       ORDER BY employer_total DESC`
    )
    .all() as PlanRow[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Benefits Cost Report</h1>
        <p className="text-sm text-gray-500">Monthly benefit costs across active enrolments.</p>
      </div>

      <BenefitsTabs active="costs" showAdmin={true} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Monthly employer cost</p>
          <p className="mt-1 text-3xl font-bold font-mono">{fmtRand(totals.employer_total)}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Employee contributions</p>
          <p className="mt-1 text-3xl font-bold font-mono">{fmtRand(totals.employee_total)}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Cost per category</p>
          <ul className="mt-2 space-y-1.5">
            {byCategory.map((c) => (
              <li key={c.category} className="flex items-center justify-between text-sm">
                <span className={categoryBadgeClass(c.category)}>{categoryLabel(c.category)}</span>
                <span className="font-mono">
                  {fmtRand(c.employer_total)} <span className="text-xs text-gray-400">employer</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 font-semibold">By employee</h2>
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="th">Employee</th>
                  <th className="th">Department</th>
                  <th className="th text-right">Employee /mo</th>
                  <th className="th text-right">Employer /mo</th>
                  <th className="th text-right">Benefits</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {byEmployee.map((r) => (
                  <tr key={r.employee_id}>
                    <td className="td font-medium text-gray-900">{r.employee_name}</td>
                    <td className="td">{r.department_name ?? "—"}</td>
                    <td className="td text-right font-mono">{fmtRand(r.employee_total)}</td>
                    <td className="td text-right font-mono">{fmtRand(r.employer_total)}</td>
                    <td className="td text-right">{r.benefit_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h2 className="mb-3 font-semibold">By plan</h2>
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="th">Plan</th>
                  <th className="th text-right">Enrolled</th>
                  <th className="th text-right">Employer /mo</th>
                  <th className="th text-right">Employee /mo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {byPlan.map((r) => (
                  <tr key={r.plan_id}>
                    <td className="td">
                      <span className="inline-flex items-center gap-2 font-medium text-gray-900">
                        {r.plan_name}
                        <span className={categoryBadgeClass(r.category)}>{categoryLabel(r.category)}</span>
                      </span>
                    </td>
                    <td className="td text-right">{r.enrolled_count}</td>
                    <td className="td text-right font-mono">{fmtRand(r.employer_total)}</td>
                    <td className="td text-right font-mono">{fmtRand(r.employee_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
