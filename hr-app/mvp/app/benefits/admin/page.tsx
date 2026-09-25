import Link from "next/link";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import BenefitsTabs from "../_components/BenefitsTabs";
import NewPlanForm from "../_components/NewPlanForm";
import PlanActiveToggle from "../_components/PlanActiveToggle";
import { categoryBadgeClass, categoryLabel } from "../_lib/benefits";

export const dynamic = "force-dynamic";

interface PlanRow {
  id: number;
  name: string;
  category: string;
  provider: string | null;
  active: number;
  tier_count: number;
  enrolled_count: number;
}

export default function BenefitsAdminPage() {
  const db = getDb();
  const user = getCurrentUser();
  if (!isHr(user)) redirect("/benefits");

  const plans = db
    .prepare(
      `SELECT bp.id, bp.name, bp.category, bp.provider, bp.active,
              (SELECT COUNT(*) FROM benefit_tiers bt WHERE bt.plan_id = bp.id) AS tier_count,
              (SELECT COUNT(*) FROM benefit_elections be
                 JOIN benefit_tiers bt2 ON bt2.id = be.tier_id
                 WHERE bt2.plan_id = bp.id AND be.status = 'active') AS enrolled_count
       FROM benefit_plans bp
       ORDER BY bp.active DESC, bp.category, bp.name`
    )
    .all() as PlanRow[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Benefit Plans</h1>
        <p className="text-sm text-gray-500">Manage the benefit plans and tiers offered to employees.</p>
      </div>

      <BenefitsTabs active="plans" showAdmin={true} />

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Plan</th>
              <th className="th">Category</th>
              <th className="th">Provider</th>
              <th className="th">Tiers</th>
              <th className="th">Enrolled</th>
              <th className="th">Status</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {plans.map((p) => (
              <tr key={p.id}>
                <td className="td">
                  <Link href={`/benefits/admin/${p.id}`} className="font-medium text-gray-900 hover:text-brand-600">
                    {p.name}
                  </Link>
                </td>
                <td className="td">
                  <span className={categoryBadgeClass(p.category)}>{categoryLabel(p.category)}</span>
                </td>
                <td className="td">{p.provider ?? "—"}</td>
                <td className="td">{p.tier_count}</td>
                <td className="td">{p.enrolled_count}</td>
                <td className="td">
                  {p.active === 1 ? <span className="badge-green">Active</span> : <span className="badge-gray">Inactive</span>}
                </td>
                <td className="td text-right">
                  <PlanActiveToggle planId={p.id} active={p.active === 1} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">New plan</h2>
        <NewPlanForm />
      </div>
    </div>
  );
}
