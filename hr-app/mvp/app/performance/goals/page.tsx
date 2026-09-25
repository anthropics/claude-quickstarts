import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import type { Goal } from "@/lib/types";
import GoalFilters from "../_components/GoalFilters";
import GoalProgressBar from "../_components/GoalProgressBar";
import GoalProgressWidget from "../_components/GoalProgressWidget";
import NewGoalForm from "../_components/NewGoalForm";
import { GOAL_STATUS_BADGE, GOAL_STATUS_LABEL, canTouchGoal } from "../_lib/perf";

export const dynamic = "force-dynamic";

const GOAL_TYPES = ["individual", "team", "company"];
const GOAL_STATUSES = ["not_started", "in_progress", "at_risk", "achieved", "missed"];

const TYPE_LABEL: Record<string, string> = {
  individual: "Individual",
  team: "Team",
  company: "Company",
};

interface GoalRow extends Goal {
  employee_name: string;
  owner_manager_id: number | null;
}

export default function GoalsPage({ searchParams }: { searchParams: { type?: string; status?: string } }) {
  const db = getDb();
  const user = getCurrentUser();
  const userIsHr = isHr(user);
  const userCanManage = canManage(user);

  const typeFilter = GOAL_TYPES.includes(searchParams.type ?? "") ? searchParams.type! : "";
  const statusFilter = GOAL_STATUSES.includes(searchParams.status ?? "") ? searchParams.status! : "";

  const where: string[] = [];
  const args: Record<string, string | number> = { uid: user.id };
  if (userIsHr) {
    where.push("1=1");
  } else if (userCanManage) {
    where.push("(g.employee_id = @uid OR e.manager_id = @uid)");
  } else {
    where.push("g.employee_id = @uid");
  }
  if (typeFilter) {
    where.push("g.type = @type");
    args.type = typeFilter;
  }
  if (statusFilter) {
    where.push("g.status = @status");
    args.status = statusFilter;
  }

  const goals = db
    .prepare(
      `SELECT g.*, e.first_name || ' ' || e.last_name AS employee_name, e.manager_id AS owner_manager_id
       FROM goals g JOIN employees e ON e.id = g.employee_id
       WHERE ${where.join(" AND ")}
       ORDER BY (g.due_date IS NULL), g.due_date, g.id`
    )
    .all(args) as GoalRow[];

  // Employee options for the new-goal form: HR picks anyone, managers their reports.
  let employeeOptions: { id: number; name: string }[] = [];
  if (userIsHr) {
    employeeOptions = db
      .prepare(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status = 'active' AND id != ? ORDER BY first_name"
      )
      .all(user.id) as { id: number; name: string }[];
  } else if (userCanManage) {
    employeeOptions = db
      .prepare(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status = 'active' AND manager_id = ? ORDER BY first_name"
      )
      .all(user.id) as { id: number; name: string }[];
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Goals</h1>
          <p className="text-sm text-gray-500">
            {userIsHr
              ? "All goals across the company."
              : userCanManage
                ? "Your goals and your direct reports' goals."
                : "Your goals."}
          </p>
        </div>
        <NewGoalForm employees={employeeOptions} />
      </div>

      <GoalFilters type={typeFilter} status={statusFilter} />

      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[900px]">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Employee</th>
              <th className="th">Goal</th>
              <th className="th">Type</th>
              <th className="th">Progress</th>
              <th className="th">Status</th>
              <th className="th">Due</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {goals.length === 0 && (
              <tr>
                <td className="td py-8 text-center text-gray-500" colSpan={7}>
                  No goals match these filters.
                </td>
              </tr>
            )}
            {goals.map((g) => (
              <tr key={g.id} className="align-top hover:bg-gray-50">
                <td className="td font-medium">{g.employee_name}</td>
                <td className="td max-w-xs">
                  <p className="font-medium text-gray-900">{g.title}</p>
                  {g.description && <p className="mt-0.5 text-xs text-gray-500">{g.description}</p>}
                </td>
                <td className="td">{TYPE_LABEL[g.type]}</td>
                <td className="td min-w-[180px]">
                  <GoalProgressBar metricType={g.metric_type} currentValue={g.current_value} targetValue={g.target_value} />
                </td>
                <td className="td">
                  <span className={GOAL_STATUS_BADGE[g.status]}>{GOAL_STATUS_LABEL[g.status]}</span>
                </td>
                <td className="td whitespace-nowrap">{g.due_date ?? "—"}</td>
                <td className="td min-w-[220px]">
                  {canTouchGoal(user, g.employee_id, g.owner_manager_id) && (
                    <GoalProgressWidget
                      goalId={g.id}
                      metricType={g.metric_type}
                      currentValue={g.current_value}
                      targetValue={g.target_value}
                      status={g.status}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
