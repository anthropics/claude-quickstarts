import Link from "next/link";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import CycleActions from "../_components/CycleActions";
import NewCycleForm from "../_components/NewCycleForm";
import { CYCLE_STATUS_BADGE } from "../_lib/perf";

export const dynamic = "force-dynamic";

interface CycleRow {
  id: number;
  name: string;
  type: string;
  period_start: string;
  period_end: string;
  status: string;
  total_reviews: number;
  submitted_reviews: number | null;
}

const TYPE_LABEL: Record<string, string> = {
  annual: "Annual",
  biannual: "Biannual",
  quarterly: "Quarterly",
  probation: "Probation",
};

const STATUS_LABEL: Record<string, string> = {
  setup: "Setup",
  active: "Active",
  closed: "Closed",
};

export default function CyclesPage() {
  const db = getDb();
  const user = getCurrentUser();

  if (!isHr(user)) {
    redirect("/performance");
  }

  const cycles = db
    .prepare(
      `SELECT c.*, COUNT(r.id) AS total_reviews,
              SUM(CASE WHEN r.status IN ('submitted', 'acknowledged') THEN 1 ELSE 0 END) AS submitted_reviews
       FROM review_cycles c
       LEFT JOIN reviews r ON r.cycle_id = c.id
       GROUP BY c.id
       ORDER BY c.period_start DESC, c.id DESC`
    )
    .all() as CycleRow[];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Review cycles</h1>
          <p className="text-sm text-gray-500">Create, launch and close performance review cycles.</p>
        </div>
        <Link href="/performance" className="btn-secondary text-sm">← Performance overview</Link>
      </div>

      <NewCycleForm />

      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[760px]">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Name</th>
              <th className="th">Type</th>
              <th className="th">Period</th>
              <th className="th">Status</th>
              <th className="th">Reviews submitted</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cycles.length === 0 && (
              <tr>
                <td className="td py-8 text-center text-gray-500" colSpan={6}>
                  No review cycles yet.
                </td>
              </tr>
            )}
            {cycles.map((c) => {
              const submitted = c.submitted_reviews ?? 0;
              const pct = c.total_reviews > 0 ? Math.round((submitted / c.total_reviews) * 100) : 0;
              return (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="td font-medium">{c.name}</td>
                  <td className="td">{TYPE_LABEL[c.type] ?? c.type}</td>
                  <td className="td whitespace-nowrap">{c.period_start} → {c.period_end}</td>
                  <td className="td">
                    <span className={CYCLE_STATUS_BADGE[c.status] ?? "badge-gray"}>{STATUS_LABEL[c.status] ?? c.status}</span>
                  </td>
                  <td className="td min-w-[180px]">
                    {c.total_reviews === 0 ? (
                      <span className="text-sm text-gray-400">No reviews generated</span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <div className="h-2 flex-1 rounded-full bg-gray-200">
                          <div className="h-2 rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="whitespace-nowrap text-xs text-gray-500">
                          {submitted}/{c.total_reviews}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="td text-right">
                    <CycleActions cycleId={c.id} status={c.status} />
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
