import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import EditTemplateForm from "../_components/EditTemplateForm";
import AddTemplateTaskForm from "../_components/AddTemplateTaskForm";
import DeleteTemplateTaskButton from "../_components/DeleteTemplateTaskButton";

export const dynamic = "force-dynamic";

interface TemplateDetail {
  id: number;
  name: string;
  description: string | null;
  department_id: number | null;
  department_name: string | null;
}

interface TemplateTaskRow {
  id: number;
  template_id: number;
  title: string;
  description: string | null;
  assignee_type: "hr" | "it" | "manager" | "new_hire";
  due_offset_days: number;
  order_index: number;
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

function offsetLabel(offset: number): string {
  if (offset === 0) return "Day 0";
  if (offset > 0) return `Day +${offset}`;
  return `Day ${offset}`;
}

export default function TemplateDetailPage({ params }: { params: { id: string } }) {
  const db = getDb();
  const user = getCurrentUser();

  if (!isHr(user)) {
    redirect("/");
  }

  const templateId = Number(params.id);
  if (isNaN(templateId)) notFound();

  const template = db
    .prepare(
      `SELECT ot.id, ot.name, ot.description, ot.department_id,
              d.name AS department_name
       FROM onboarding_templates ot
       LEFT JOIN departments d ON d.id = ot.department_id
       WHERE ot.id = ?`
    )
    .get(templateId) as TemplateDetail | undefined;

  if (!template) notFound();

  const tasks = db
    .prepare(
      `SELECT * FROM onboarding_template_tasks
       WHERE template_id = ?
       ORDER BY order_index, id`
    )
    .all(templateId) as TemplateTaskRow[];

  const departments = db
    .prepare("SELECT id, name FROM departments ORDER BY name")
    .all() as { id: number; name: string }[];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-sm text-gray-500">
            <Link href="/onboarding" className="hover:text-brand-600">Onboarding</Link>
            <span>/</span>
            <Link href="/onboarding/templates" className="hover:text-brand-600">Templates</Link>
            <span>/</span>
            <span>{template.name}</span>
          </div>
          <h1 className="text-2xl font-bold">{template.name}</h1>
          <p className="text-sm text-gray-500">
            {template.description ?? "No description."}
            {" · "}
            {template.department_name ?? "All departments"}
          </p>
        </div>
        <EditTemplateForm
          templateId={templateId}
          initialName={template.name}
          initialDescription={template.description}
          initialDepartmentId={template.department_id}
          departments={departments}
        />
      </div>

      {/* Task list */}
      <div className="card">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">Tasks ({tasks.length})</h2>
        </div>
        {tasks.length === 0 ? (
          <p className="text-sm text-gray-500">No tasks in this template yet.</p>
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-gray-100 p-3"
              >
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-sm">{task.title}</p>
                    {assigneeBadge(task.assignee_type)}
                    <span className="text-xs text-gray-400">{offsetLabel(task.due_offset_days)}</span>
                  </div>
                  {task.description && (
                    <p className="mt-1 text-xs text-gray-500">{task.description}</p>
                  )}
                </div>
                <DeleteTemplateTaskButton templateId={templateId} taskId={task.id} />
              </div>
            ))}
          </div>
        )}

        <div className="mt-6 border-t border-gray-100 pt-4">
          <AddTemplateTaskForm templateId={templateId} />
        </div>
      </div>
    </div>
  );
}
