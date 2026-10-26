import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { LetterTemplate } from "./_lib/data";
import TypeBadge from "./_components/TypeBadge";

export const dynamic = "force-dynamic";

interface RecentLetterRow {
  id: number;
  title: string;
  created_at: string;
  employee_name: string;
  created_by_name: string | null;
}

export default function LettersPage() {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return (
      <div className="card max-w-lg">
        <h1 className="font-semibold">Access denied</h1>
        <p className="mt-1 text-sm text-gray-500">Only HR and admins can manage HR letters.</p>
        <Link href="/" className="btn-secondary mt-4">
          Back to dashboard
        </Link>
      </div>
    );
  }

  const db = getDb();
  const templates = db
    .prepare("SELECT * FROM letter_templates ORDER BY name")
    .all() as LetterTemplate[];
  const recent = db
    .prepare(
      `SELECT gl.id, gl.title, gl.created_at,
              e.first_name || ' ' || e.last_name AS employee_name,
              c.first_name || ' ' || c.last_name AS created_by_name
       FROM generated_letters gl
       JOIN employees e ON e.id = gl.employee_id
       LEFT JOIN employees c ON c.id = gl.created_by
       ORDER BY gl.created_at DESC, gl.id DESC
       LIMIT 25`
    )
    .all() as RecentLetterRow[];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">HR Letters</h1>
          <p className="text-sm text-gray-500">
            Generate official letters from templates and manage the template library.
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/letters/templates/new" className="btn-secondary">
            New template
          </Link>
          <Link href="/letters/generate" className="btn-primary">
            Generate letter
          </Link>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Templates</h2>
        {templates.length === 0 ? (
          <p className="text-sm text-gray-500">No templates yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="th">Name</th>
                  <th className="th">Type</th>
                  <th className="th">Created</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {templates.map((t) => (
                  <tr key={t.id}>
                    <td className="td font-medium text-gray-900">{t.name}</td>
                    <td className="td"><TypeBadge type={t.type} /></td>
                    <td className="td text-gray-500">{t.created_at.slice(0, 10)}</td>
                    <td className="td text-right">
                      <Link
                        href={`/letters/templates/${t.id}`}
                        className="text-sm font-medium text-brand-600 hover:underline"
                      >
                        Edit
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Recently generated</h2>
        {recent.length === 0 ? (
          <p className="text-sm text-gray-500">No letters generated yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="th">Employee</th>
                  <th className="th">Title</th>
                  <th className="th">Created by</th>
                  <th className="th">Date</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recent.map((l) => (
                  <tr key={l.id}>
                    <td className="td font-medium text-gray-900">{l.employee_name}</td>
                    <td className="td">{l.title}</td>
                    <td className="td">{l.created_by_name ?? "—"}</td>
                    <td className="td text-gray-500">{l.created_at.slice(0, 10)}</td>
                    <td className="td text-right">
                      <Link
                        href={`/letters/${l.id}`}
                        className="text-sm font-medium text-brand-600 hover:underline"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
