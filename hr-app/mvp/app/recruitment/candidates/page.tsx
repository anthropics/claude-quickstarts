import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default function CandidatesPage({ searchParams }: { searchParams: { q?: string } }) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return <div className="card text-sm text-gray-500">Access restricted to HR and admins.</div>;
  }

  const db = getDb();
  const q = searchParams.q?.trim() ?? "";

  const candidates = db.prepare(`
    SELECT c.*,
      COUNT(DISTINCT a.id) AS application_count
    FROM candidates c
    LEFT JOIN applications a ON a.candidate_id = c.id
    WHERE (? = '' OR c.first_name || ' ' || c.last_name LIKE ? OR c.email LIKE ?)
    GROUP BY c.id
    ORDER BY c.created_at DESC
  `).all(q, `%${q}%`, `%${q}%`) as {
    id: number; first_name: string; last_name: string; email: string;
    phone: string | null; cv_filename: string | null; cv_file_id: number | null;
    source: string; created_at: string; application_count: number;
  }[];

  const sourceColour: Record<string, string> = {
    linkedin: "badge-blue", indeed: "badge-green", direct: "badge-gray",
    referral: "badge-yellow", internal: "badge-yellow", careers: "badge-green",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Candidate Directory</h1>
          <p className="text-sm text-gray-500">{candidates.length} candidate{candidates.length !== 1 ? "s" : ""}</p>
        </div>
        <Link href="/recruitment" className="btn-secondary">← Back to Recruitment</Link>
      </div>

      <form method="get" className="flex gap-2">
        <input name="q" defaultValue={q} placeholder="Search by name or email…" className="input max-w-xs" />
        <button type="submit" className="btn-primary">Search</button>
        {q && <Link href="/recruitment/candidates" className="btn-secondary">Clear</Link>}
      </form>

      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="border-b border-gray-100 bg-gray-50">
            <tr>
              <th className="th">Name</th>
              <th className="th">Email</th>
              <th className="th">Phone</th>
              <th className="th">Source</th>
              <th className="th">CV</th>
              <th className="th">Applications</th>
              <th className="th">Added</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {candidates.length === 0 && (
              <tr><td colSpan={7} className="td text-center text-gray-400 py-8">No candidates found.</td></tr>
            )}
            {candidates.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="td font-medium">{c.first_name} {c.last_name}</td>
                <td className="td">{c.email}</td>
                <td className="td text-gray-500">{c.phone ?? "—"}</td>
                <td className="td">
                  <span className={sourceColour[c.source] ?? "badge-gray"}>{c.source}</span>
                </td>
                <td className="td text-gray-500">
                  {c.cv_file_id ? (
                    <a
                      href={`/api/files/${c.cv_file_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-brand-600 hover:underline"
                    >
                      View CV
                    </a>
                  ) : (
                    c.cv_filename ?? "—"
                  )}
                </td>
                <td className="td">{c.application_count}</td>
                <td className="td text-gray-500">{c.created_at.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
