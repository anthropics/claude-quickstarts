import Link from "next/link";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { BenefitTier } from "@/lib/types";
import BenefitsTabs from "../../_components/BenefitsTabs";
import EndElectionButton from "../../_components/EndElectionButton";
import EnrolEmployeeForm from "../../_components/EnrolEmployeeForm";
import { categoryBadgeClass, categoryLabel, fmtRand } from "../../_lib/benefits";

export const dynamic = "force-dynamic";

interface ElectionRow {
  id: number;
  status: string;
  effective_from: string;
  employee_name: string;
  plan_id: number;
  plan_name: string;
  category: string;
  tier_name: string;
  monthly_cost_employee: number;
  monthly_cost_employer: number;
}

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return <span className="badge-green">Active</span>;
    case "pending":
      return <span className="badge-yellow">Pending</span>;
    case "ended":
      return <span className="badge-gray">Ended</span>;
    default:
      return <span className="badge-gray">{status}</span>;
  }
}

export default function EnrolmentsPage({ searchParams }: { searchParams: { plan?: string } }) {
  const db = getDb();
  const user = getCurrentUser();
  if (!isHr(user)) redirect("/benefits");

  const planFilter = Number(searchParams.plan);
  const hasFilter = Number.isInteger(planFilter) && planFilter > 0;

  const plans = db
    .prepare("SELECT id, name, active FROM benefit_plans ORDER BY category, name")
    .all() as { id: number; name: string; active: number }[];

  const elections = db
    .prepare(
      `SELECT be.id, be.status, be.effective_from,
              e.first_name || ' ' || e.last_name AS employee_name,
              bp.id AS plan_id, bp.name AS plan_name, bp.category,
              bt.name AS tier_name, bt.monthly_cost_employee, bt.monthly_cost_employer
       FROM benefit_elections be
       JOIN employees e ON e.id = be.employee_id
       JOIN benefit_tiers bt ON bt.id = be.tier_id
       JOIN benefit_plans bp ON bp.id = bt.plan_id
       ${hasFilter ? "WHERE bp.id = ?" : ""}
       ORDER BY CASE be.status WHEN 'active' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
                bp.category, bp.name, employee_name`
    )
    .all(...(hasFilter ? [planFilter] : [])) as ElectionRow[];

  // Enrol form data: active employees + tiers of active plans, grouped by plan.
  const employees = db
    .prepare(
      "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status = 'active' ORDER BY first_name, last_name"
    )
    .all() as { id: number; name: string }[];
  const activeTiers = db
    .prepare(
      `SELECT bt.* FROM benefit_tiers bt
       JOIN benefit_plans bp ON bp.id = bt.plan_id
       WHERE bp.active = 1
       ORDER BY bt.monthly_cost_employee, bt.id`
    )
    .all() as BenefitTier[];
  const planGroups = plans
    .filter((p) => p.active === 1)
    .map((p) => ({
      id: p.id,
      name: p.name,
      tiers: activeTiers
        .filter((t) => t.plan_id === p.id)
        .map((t) => ({
          id: t.id,
          name: t.name,
          monthly_cost_employee: t.monthly_cost_employee,
          monthly_cost_employer: t.monthly_cost_employer,
        })),
    }))
    .filter((p) => p.tiers.length > 0);

  const filterPill = (href: string, label: string, selected: boolean) => (
    <Link
      href={href}
      className={`rounded-full border px-3 py-1 text-xs font-medium ${
        selected
          ? "border-brand-600 bg-brand-100 text-brand-700"
          : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Benefit Enrolments</h1>
        <p className="text-sm text-gray-500">All employee benefit elections across plans.</p>
      </div>

      <BenefitsTabs active="enrolments" showAdmin={true} />

      <div className="flex flex-wrap gap-2">
        {filterPill("/benefits/admin/enrolments", "All plans", !hasFilter)}
        {plans.map((p) =>
          filterPill(`/benefits/admin/enrolments?plan=${p.id}`, p.name, hasFilter && planFilter === p.id)
        )}
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Employee</th>
              <th className="th">Plan</th>
              <th className="th">Tier</th>
              <th className="th">Status</th>
              <th className="th">Effective from</th>
              <th className="th text-right">Employee /mo</th>
              <th className="th text-right">Employer /mo</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {elections.length === 0 && (
              <tr>
                <td className="td text-gray-500" colSpan={8}>No enrolments found.</td>
              </tr>
            )}
            {elections.map((el) => (
              <tr key={el.id}>
                <td className="td font-medium text-gray-900">{el.employee_name}</td>
                <td className="td">
                  <span className="inline-flex items-center gap-2">
                    {el.plan_name}
                    <span className={categoryBadgeClass(el.category)}>{categoryLabel(el.category)}</span>
                  </span>
                </td>
                <td className="td">{el.tier_name}</td>
                <td className="td">{statusBadge(el.status)}</td>
                <td className="td">{el.effective_from}</td>
                <td className="td text-right font-mono">{fmtRand(el.monthly_cost_employee)}</td>
                <td className="td text-right font-mono">{fmtRand(el.monthly_cost_employer)}</td>
                <td className="td text-right">
                  {el.status !== "ended" && <EndElectionButton electionId={el.id} label="End" />}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Enrol employee</h2>
        <EnrolEmployeeForm employees={employees} plans={planGroups} />
      </div>
    </div>
  );
}
