import Link from "next/link";
import { listOpenPostings } from "@/app/api/careers/_lib/postings";

export const dynamic = "force-dynamic";

const EMPLOYMENT_TYPE_LABEL: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  intern: "Internship",
};

export default function CareersPage() {
  const postings = listOpenPostings();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Join our team</h1>
        <p className="mt-2 text-sm text-gray-600">
          We&apos;re building great things at Acme. Browse our open positions below —
          we&apos;d love to hear from you.
        </p>
      </div>

      {postings.length === 0 ? (
        <div className="card text-center text-sm text-gray-500">
          There are no open positions right now. Please check back soon.
        </div>
      ) : (
        <div className="space-y-3">
          {postings.map((p) => (
            <Link
              key={p.id}
              href={`/careers/${p.public_slug}`}
              className="card block transition-shadow hover:border-brand-300 hover:shadow-md"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h2 className="font-semibold text-gray-900">{p.title}</h2>
                  <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-500">
                    {p.department_name && <span>{p.department_name}</span>}
                    {p.department_name && p.location && <span>·</span>}
                    {p.location && <span>{p.location}</span>}
                    <span>·</span>
                    <span>{EMPLOYMENT_TYPE_LABEL[p.employment_type] ?? p.employment_type}</span>
                  </div>
                </div>
                <div className="text-right">
                  {p.posted_at && (
                    <p className="text-xs text-gray-400">Posted {p.posted_at.slice(0, 10)}</p>
                  )}
                  <span className="mt-1 inline-block text-sm font-medium text-brand-600">
                    View &amp; apply →
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
