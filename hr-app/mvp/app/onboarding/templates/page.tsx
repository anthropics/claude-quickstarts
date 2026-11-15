import Link from "next/link";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import NewTemplateForm from "./_components/NewTemplateForm";

export const dynamic = "force-dynamic";

interface TemplateRow {
  id: number;
  name: string;
  description: string | null;
  department_id: number | null;
  department_name: string | null;
  task_count: number;
}

export default function TemplatesPage() {
  const db = getDb();
  const user = getCurrentUser();

  if (!isHr(user)) {
    redirect("/");
  }

  const templates = db
    .prepare(
      `SELECT ot.id, ot.name, ot.description, ot.department_id,
              d.name AS department_name,
              COUNT(tt.id) AS task_count
       FROM onboarding_templates ot
       LEFT JOIN departments d ON d.id = ot.department_id
       LEFT JOIN onboarding_template_tasks tt ON tt.template_id = ot.id
       GROUP BY ot.id
       ORDER BY ot.name`
    )
    .all() as TemplateRow[];

  const departments = db
    .prepare("SELECT id, name FROM departments ORDER BY name")
    .all() as { id: number; name: string }[];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-sm text-gray-500">
            <Link href="/onboarding" className="hover:text-brand-600">Onboarding</Link>
            <span>/</span>
            <span>Templates</span>
          </div>
          <h1 className="text-2xl font-bold">Onboarding Templates</h1>
          <p className="text-sm text-gray-500">Manage reusable onboarding checklists.</p>
        </div>
        <NewTemplateForm departments={departments} />
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Template Name</th>
              <th className="th">Description</th>
              <th className="th">Department</th>
              <th className="th text-right">Tasks</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {templates.length === 0 && (
              <tr>
                <td className="td py-8 text-center text-gray-500" colSpan={5}>
                  No templates yet. Create one to get started.
                </td>
              </tr>
            )}
            {templates.map((tpl) => (
              <tr key={tpl.id} className="hover:bg-gray-50">
                <td className="td">
                  <Link
                    href={`/onboarding/templates/${tpl.id}`}
                    className="font-medium text-brand-600 hover:underline"
                  >
                    {tpl.name}
                  </Link>
                </td>
                <td className="td max-w-xs text-sm text-gray-500">
                  {tpl.description ?? <span className="text-gray-300">—</span>}
                </td>
                <td className="td">
                  {tpl.department_name ? (
                    <span className="badge-gray">{tpl.department_name}</span>
                  ) : (
                    <span className="text-gray-400 text-sm">All departments</span>
                  )}
                </td>
                <td className="td text-right font-medium">{tpl.task_count}</td>
                <td className="td text-right">
                  <Link
                    href={`/onboarding/templates/${tpl.id}`}
                    className="text-sm text-brand-600 hover:underline"
                  >
                    Edit
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
