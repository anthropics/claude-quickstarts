import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { GeneratedLetter } from "../_lib/data";
import PrintButton from "../_components/PrintButton";

export const dynamic = "force-dynamic";

type LetterRow = GeneratedLetter & {
  employee_name: string;
  employee_number: string;
  created_by_name: string | null;
};

export default function LetterViewPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) notFound();

  const user = getCurrentUser();
  const db = getDb();
  const letter = db
    .prepare(
      `SELECT gl.*,
              e.first_name || ' ' || e.last_name AS employee_name,
              e.employee_number,
              c.first_name || ' ' || c.last_name AS created_by_name
       FROM generated_letters gl
       JOIN employees e ON e.id = gl.employee_id
       LEFT JOIN employees c ON c.id = gl.created_by
       WHERE gl.id = ?`
    )
    .get(id) as LetterRow | undefined;
  if (!letter) notFound();

  // Access: HR, or the employee the letter is about.
  if (!isHr(user) && user.id !== letter.employee_id) {
    return (
      <div className="card max-w-lg">
        <h1 className="font-semibold">Access denied</h1>
        <p className="mt-1 text-sm text-gray-500">You can only view letters issued to you.</p>
        <Link href="/" className="btn-secondary mt-4">
          Back to dashboard
        </Link>
      </div>
    );
  }

  const backHref = isHr(user) ? "/letters" : "/";
  const backLabel = isHr(user) ? "HR Letters" : "Dashboard";

  return (
    <>
      <div className="mb-6 print:hidden">
        <Link href={backHref} className="text-sm font-medium text-brand-600 hover:underline">
          ← {backLabel}
        </Link>
      </div>

      {/* Letter document */}
      <div className="mx-auto max-w-2xl space-y-6 rounded-xl border border-gray-200 bg-white p-8 shadow-sm print:border-0 print:p-0 print:shadow-none">
        <div className="flex items-start justify-between border-b border-gray-200 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 font-bold text-white print:hidden">
                H
              </div>
              <span className="text-xl font-bold">HRCore</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Acme (Pty) Ltd</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Official letter</p>
            <p className="mt-1 text-sm text-gray-700">{letter.created_at.slice(0, 10)}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 border-b border-gray-200 pb-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Employee</p>
            <p className="mt-1 text-base font-semibold">{letter.employee_name}</p>
            <p className="text-sm font-mono text-gray-600">{letter.employee_number}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Issued by</p>
            <p className="mt-1 text-sm text-gray-700">{letter.created_by_name ?? "—"}</p>
            <p className="text-sm text-gray-500">People &amp; Culture</p>
          </div>
        </div>

        <div>
          <h1 className="mb-4 text-lg font-bold">{letter.title}</h1>
          {/* Rendered as a text node on purpose — letter content is plain text. */}
          <p className="whitespace-pre-line text-sm leading-relaxed text-gray-800">{letter.content}</p>
        </div>

        <div className="border-t border-gray-200 pt-4 text-center text-xs text-gray-400">
          This letter was generated via HRCore. · Acme (Pty) Ltd
        </div>
      </div>

      <div className="mx-auto mt-4 max-w-2xl text-right print:hidden">
        <PrintButton />
      </div>
    </>
  );
}
