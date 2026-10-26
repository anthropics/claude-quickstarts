import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { BenefitPlan, BenefitTier } from "@/lib/types";
import BenefitsTabs from "./_components/BenefitsTabs";
import EnrolButton from "./_components/EnrolButton";
import EndElectionButton from "./_components/EndElectionButton";
import { categoryBadgeClass, categoryLabel, fmtRand } from "./_lib/benefits";

export const dynamic = "force-dynamic";

interface MyElectionRow {
  id: number;
  effective_from: string;
  tier_id: number;
  tier_name: string;
  monthly_cost_employee: number;
  monthly_cost_employer: number;
  plan_id: number;
  plan_name: string;
  category: string;
  provider: string | null;
}

export default function MyBenefitsPage() {
  const db = getDb();
  const user = getCurrentUser();

  const elections = db
    .prepare(
      `SELECT be.id, be.effective_from,
              bt.id AS tier_id, bt.name AS tier_name,
              bt.monthly_cost_employee, bt.monthly_cost_employer,
              bp.id AS plan_id, bp.name AS plan_name, bp.category, bp.provider
       FROM benefit_elections be
       JOIN benefit_tiers bt ON bt.id = be.tier_id
       JOIN benefit_plans bp ON bp.id = bt.plan_id
       WHERE be.employee_id = ? AND be.status = 'active'
       ORDER BY bp.category, bp.name`
    )
    .all(user.id) as MyElectionRow[];

  const myMonthly = elections.reduce((s, e) => s + e.monthly_cost_employee, 0);
  const employerMonthly = elections.reduce((s, e) => s + e.monthly_cost_employer, 0);
  const enrolledTierIds = new Set(elections.map((e) => e.tier_id));
  const enrolledPlanIds = new Set(elections.map((e) => e.plan_id));

  const activePlans = db
    .prepare("SELECT * FROM benefit_plans WHERE active = 1 ORDER BY category, name")
    .all() as BenefitPlan[];
  const allTiers = db
    .prepare("SELECT * FROM benefit_tiers ORDER BY monthly_cost_employee, id")
    .all() as BenefitTier[];

  const availablePlans = activePlans
    .map((plan) => ({
      plan,
      tiers: allTiers.filter((t) => t.plan_id === plan.id && !enrolledTierIds.has(t.id)),
    }))
    .filter((p) => p.tiers.length > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Benefits</h1>
        <p className="text-sm text-gray-500">Your benefit enrolments and the plans available to you.</p>
      </div>

      <BenefitsTabs active="my" showAdmin={isHr(user)} />

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">My monthly contribution</p>
          <p className="mt-1 text-3xl font-bold font-mono">{fmtRand(myMonthly)}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Employer contribution</p>
          <p className="mt-1 text-3xl font-bold font-mono">{fmtRand(employerMonthly)}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Active benefits</p>
          <p className="mt-1 text-3xl font-bold">{elections.length}</p>
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="font-semibold">My active benefits</h2>
        {elections.length === 0 ? (
          <div className="card text-sm text-gray-500">
            You are not enrolled in any benefits yet. Pick a plan below to get started.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {elections.map((e) => (
              <div key={e.id} className="card flex flex-col">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{e.plan_name}</p>
                    {e.provider && <p className="text-xs text-gray-500">{e.provider}</p>}
                  </div>
                  <span className={categoryBadgeClass(e.category)}>{categoryLabel(e.category)}</span>
                </div>
                <dl className="mt-3 space-y-1.5 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Tier</dt>
                    <dd className="font-medium">{e.tier_name}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">My cost</dt>
                    <dd className="font-mono">{fmtRand(e.monthly_cost_employee)}/mo</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Employer cost</dt>
                    <dd className="font-mono">{fmtRand(e.monthly_cost_employer)}/mo</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Effective from</dt>
                    <dd>{e.effective_from}</dd>
                  </div>
                </dl>
                <div className="mt-4 border-t border-gray-100 pt-3">
                  <EndElectionButton electionId={e.id} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">Available plans</h2>
        {availablePlans.length === 0 ? (
          <div className="card text-sm text-gray-500">You are enrolled in every available plan and tier.</div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {availablePlans.map(({ plan, tiers }) => {
              const switching = enrolledPlanIds.has(plan.id);
              return (
                <div key={plan.id} className="card">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{plan.name}</p>
                      {plan.provider && <p className="text-xs text-gray-500">{plan.provider}</p>}
                    </div>
                    <span className={categoryBadgeClass(plan.category)}>{categoryLabel(plan.category)}</span>
                  </div>
                  {plan.description && <p className="mt-2 text-sm text-gray-600">{plan.description}</p>}
                  {switching && (
                    <p className="mt-2 text-xs text-gray-400">
                      You are already on a tier of this plan — enrolling in another tier ends your current one.
                    </p>
                  )}
                  <div className="mt-3 space-y-2">
                    {tiers.map((t) => (
                      <div
                        key={t.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-100 p-3"
                      >
                        <div>
                          <p className="text-sm font-medium">{t.name}</p>
                          <p className="text-xs text-gray-500">
                            You pay <span className="font-mono">{fmtRand(t.monthly_cost_employee)}</span>/mo · employer
                            pays <span className="font-mono">{fmtRand(t.monthly_cost_employer)}</span>/mo
                            {t.description ? ` · ${t.description}` : ""}
                          </p>
                        </div>
                        <EnrolButton tierId={t.id} switching={switching} />
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
