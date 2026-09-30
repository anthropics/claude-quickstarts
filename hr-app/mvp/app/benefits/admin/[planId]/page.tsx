import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { BenefitPlan } from "@/lib/types";
import BenefitsTabs from "../../_components/BenefitsTabs";
import EditPlanForm from "../../_components/EditPlanForm";
import AddTierForm from "../../_components/AddTierForm";
import PlanActiveToggle from "../../_components/PlanActiveToggle";
import { categoryBadgeClass, categoryLabel, fmtRand } from "../../_lib/benefits";

export const dynamic = "force-dynamic";

interface TierRow {
  id: number;
  name: string;
  monthly_cost_employee: number;
  monthly_cost_employer: number;
  description: string | null;
  enrolled_count: number;
}

export default function PlanDetailPage({ params }: { params: { planId: string } }) {
  const db = getDb();
  const user = getCurrentUser();
  if (!isHr(user)) redirect("/benefits");

  const planId = Number(params.planId);
  if (isNaN(planId)) notFound();

  const plan = db.prepare("SELECT * FROM benefit_plans WHERE id = ?").get(planId) as BenefitPlan | undefined;
  if (!plan) notFound();

  const tiers = db
    .prepare(
      `SELECT bt.id, bt.name, bt.monthly_cost_employee, bt.monthly_cost_employer, bt.description,
              (SELECT COUNT(*) FROM benefit_elections be WHERE be.tier_id = bt.id AND be.status = 'active') AS enrolled_count
       FROM benefit_tiers bt
       WHERE bt.plan_id = ?
       ORDER BY bt.monthly_cost_employee, bt.id`
    )
    .all(planId) as TierRow[];

  const enrolledTotal = tiers.reduce((s, t) => s + t.enrolled_count, 0);

  return (
    <div className="space-y-6">
      <div>
        <div className="mb-1 flex items-center gap-2 text-sm text-gray-500">
          <Link href="/benefits/admin" className="hover:text-brand-600">Benefit Plans</Link>
          <span>/</span>
          <span>{plan.name}</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold">{plan.name}</h1>
          <span className={categoryBadgeClass(plan.category)}>{categoryLabel(plan.category)}</span>
          {plan.active === 1 ? <span className="badge-green">Active</span> : <span className="badge-gray">Inactive</span>}
          <PlanActiveToggle planId={plan.id} active={plan.active === 1} />
        </div>
        <p className="text-sm text-gray-500">
          {plan.provider ?? "No provider"} · {enrolledTotal} active enrolment{enrolledTotal === 1 ? "" : "s"}
        </p>
      </div>

      <BenefitsTabs active="plans" showAdmin={true} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="th">Tier</th>
                  <th className="th">Employee cost</th>
                  <th className="th">Employer cost</th>
                  <th className="th">Enrolled</th>
                  <th className="th">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {tiers.length === 0 && (
                  <tr>
                    <td className="td text-gray-500" colSpan={5}>No tiers yet — add one below.</td>
                  </tr>
                )}
                {tiers.map((t) => (
                  <tr key={t.id}>
                    <td className="td font-medium text-gray-900">{t.name}</td>
                    <td className="td font-mono">{fmtRand(t.monthly_cost_employee)}/mo</td>
                    <td className="td font-mono">{fmtRand(t.monthly_cost_employer)}/mo</td>
                    <td className="td">{t.enrolled_count}</td>
                    <td className="td text-gray-500">{t.description ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2 className="mb-3 font-semibold">Add tier</h2>
            <AddTierForm planId={plan.id} />
          </div>
        </div>

        <div className="card self-start">
          <h2 className="mb-3 font-semibold">Plan details</h2>
          <EditPlanForm
            planId={plan.id}
            initialName={plan.name}
            initialCategory={plan.category}
            initialProvider={plan.provider}
            initialDescription={plan.description}
          />
        </div>
      </div>
    </div>
  );
}
