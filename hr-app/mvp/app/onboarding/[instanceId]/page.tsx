import { notFound } from "next/navigation";
import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr, canManage } from "@/lib/session";
import { Icon } from "@/components/icons";
import TaskCompleteWidget from "../_components/TaskCompleteWidget";
import AdHocTaskForm from "../_components/AdHocTaskForm";
import PrintButton from "../_components/PrintButton";

export const dynamic = "force-dynamic";

interface TaskRow {
  id: number;
  instance_id: number;
  template_task_id: number | null;
  title: string;
  description: string | null;
  assignee_type: "hr" | "it" | "manager" | "new_hire";
  assigned_to_id: number | null;
  assigned_to_name: string | null;
  due_date: string | null;
  status: "pending" | "in_progress" | "completed" | "skipped";
  completed_at: string | null;
  notes: string | null;
  order_index: number;
}

interface InstanceDetail {
  id: number;
  employee_id: number;
  template_id: number;
  created_at: string;
  completed_at: string | null;
  employee_name: string;
  start_date: string;
  template_name: string;
  manager_id: number | null;
}

function assigneeBadge(type: string) {
  switch (type) {
    case "hr": return <span className="badge-blue">HR</span>;
    case "it": return <span className="badge-gray">IT</span>;
    case "manager": return <span className="badge-yellow">Manager</span>;
    case "new_hire": return <span className="badge-green">New Hire</span>;
    default: return <span className="badge-gray">{type}</span>;
  }
}

function statusBadge(status: string) {
  switch (status) {
    case "completed": return <span className="badge-green">Completed</span>;
    case "in_progress": return <span className="badge-yellow">In Progress</span>;
    case "skipped": return <span className="badge-gray">Skipped</span>;
    default: return <span className="badge-gray">Pending</span>;
  }
}

export default function InstancePage({ params }: { params: { instanceId: string } }) {
  const db = getDb();
  const user = getCurrentUser();
  const userIsHr = isHr(user);
  const userCanManage = canManage(user);

  const instanceId = Number(params.instanceId);
  if (isNaN(instanceId)) notFound();

  const instance = db
    .prepare(
      `SELECT oi.id, oi.employee_id, oi.template_id, oi.created_at, oi.completed_at,
              e.first_name || ' ' || e.last_name AS employee_name,
              e.start_date,
              e.manager_id,
              ot.name AS template_name
       FROM onboarding_instances oi
       JOIN employees e ON e.id = oi.employee_id
       JOIN onboarding_templates ot ON ot.id = oi.template_id
       WHERE oi.id = ?`
    )
    .get(instanceId) as InstanceDetail | undefined;

  if (!instance) notFound();

  // Access control
  const isOwner = instance.employee_id === user.id;
  const isTheirManager = userCanManage && instance.manager_id === user.id;
  if (!userIsHr && !isOwner && !isTheirManager) notFound();

  const tasks = db
    .prepare(
      `SELECT t.*,
              e.first_name || ' ' || e.last_name AS assigned_to_name
       FROM onboarding_tasks t
       LEFT JOIN employees e ON e.id = t.assigned_to_id
       WHERE t.instance_id = ?
       ORDER BY t.order_index, t.id`
    )
    .all(instanceId) as TaskRow[];

  const today = new Date().toISOString().slice(0, 10);
  const totalTasks = tasks.length;
  const completedTasks = tasks.filter((t) => t.status === "completed").length;
  const pct = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;
  const allDone = totalTasks > 0 && completedTasks === totalTasks;

  // Group by assignee_type
  const groups: { label: string; type: string; tasks: TaskRow[] }[] = [
    { label: "My Tasks", type: "new_hire", tasks: tasks.filter((t) => t.assignee_type === "new_hire") },
    { label: "HR Tasks", type: "hr", tasks: tasks.filter((t) => t.assignee_type === "hr") },
    { label: "Manager Tasks", type: "manager", tasks: tasks.filter((t) => t.assignee_type === "manager") },
    { label: "IT Tasks", type: "it", tasks: tasks.filter((t) => t.assignee_type === "it") },
  ].filter((g) => g.tasks.length > 0);

  // Employees for ad-hoc task form
  const employees = userIsHr
    ? (db
        .prepare("SELECT id, first_name, last_name FROM employees WHERE status = 'active' ORDER BY first_name")
        .all() as { id: number; first_name: string; last_name: string }[])
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-sm text-gray-500">
            <Link href="/onboarding" className="hover:text-brand-600">Onboarding</Link>
            <span>/</span>
            <span>{instance.employee_name}</span>
          </div>
          <h1 className="text-2xl font-bold">{instance.employee_name}</h1>
          <p className="text-sm text-gray-500">
            {instance.template_name} · Started {instance.created_at.slice(0, 10)}
            {instance.completed_at && (
              <> · Completed {instance.completed_at.slice(0, 10)}</>
            )}
          </p>
        </div>
        <PrintButton />
      </div>

      {/* Progress bar */}
      <div className="card">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-medium text-gray-700">
            {completedTasks} of {totalTasks} tasks completed — {pct}%
          </p>
          {instance.completed_at && <span className="badge-green">All done!</span>}
        </div>
        <div className="h-2 rounded-full bg-gray-200">
          <div
            className="h-2 rounded-full bg-brand-600 transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* All done banner */}
      {allDone && (
        <div className="rounded-xl bg-green-50 px-6 py-4 text-center">
          <p className="flex items-center justify-center gap-2 text-lg font-semibold text-green-700"><Icon name="checkCircle" size={22} /> All done!</p>
          <p className="text-sm text-green-600">
            {instance.employee_name} has completed all onboarding tasks.
          </p>
        </div>
      )}

      {/* Task groups */}
      {groups.map((group) => (
        <div key={group.type} className="card">
          <h3 className="mb-4 font-semibold text-gray-700">{group.label}</h3>
          <div className="space-y-3">
            {group.tasks.map((task) => {
              const isOverdue =
                task.due_date &&
                task.due_date < today &&
                task.status !== "completed" &&
                task.status !== "skipped";

              // Show complete widget if:
              // - task is not completed/skipped
              // - user is HR, or user is manager, or user is the new_hire AND it's a new_hire task
              const canComplete =
                task.status !== "completed" &&
                task.status !== "skipped" &&
                (userIsHr ||
                  isTheirManager ||
                  (isOwner && task.assignee_type === "new_hire"));

              return (
                <div key={task.id} className="rounded-lg border border-gray-100 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className={`font-medium ${task.status === "completed" ? "line-through text-gray-400" : ""}`}>
                          {task.title}
                        </p>
                        {assigneeBadge(task.assignee_type)}
                        {statusBadge(task.status)}
                      </div>
                      {task.description && (
                        <p className="mt-1 text-sm text-gray-500">{task.description}</p>
                      )}
                      <div className="mt-1 flex flex-wrap gap-3 text-xs text-gray-400">
                        {task.due_date && (
                          <span className={isOverdue ? "font-medium text-red-600" : ""}>
                            Due: {task.due_date}
                            {isOverdue && " (overdue)"}
                          </span>
                        )}
                        {task.assigned_to_name && (
                          <span>Assigned to: {task.assigned_to_name}</span>
                        )}
                        {task.completed_at && (
                          <span>Completed: {task.completed_at.slice(0, 10)}</span>
                        )}
                      </div>
                      {task.notes && (
                        <p className="mt-1 text-xs text-gray-500 italic">Notes: {task.notes}</p>
                      )}
                    </div>
                  </div>
                  {canComplete && (
                    <TaskCompleteWidget taskId={task.id} currentNotes={task.notes} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Ad-hoc task form (HR only) */}
      {userIsHr && (
        <div className="card">
          <h3 className="mb-4 font-semibold text-gray-700">Add Ad-hoc Task</h3>
          <AdHocTaskForm instanceId={instanceId} employees={employees} />
        </div>
      )}
    </div>
  );
}
