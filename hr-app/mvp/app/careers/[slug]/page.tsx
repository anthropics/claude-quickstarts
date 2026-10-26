import Link from "next/link";
import { notFound } from "next/navigation";
import { getOpenPostingBySlug } from "@/app/api/careers/_lib/postings";
import ApplyForm from "../_components/ApplyForm";

export const dynamic = "force-dynamic";

const EMPLOYMENT_TYPE_LABEL: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  intern: "Internship",
};

export default function CareersPostingPage({ params }: { params: { slug: string } }) {
  const posting = getOpenPostingBySlug(params.slug);
  if (!posting) notFound();

  return (
    <div className="space-y-6">
      <div>
        <Link href="/careers" className="text-sm text-brand-600 hover:underline">
          ← All open positions
        </Link>
        <h1 className="mt-1 text-3xl font-bold">{posting.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-500">
          {posting.department_name && <span>{posting.department_name}</span>}
          {posting.department_name && posting.location && <span>·</span>}
          {posting.location && <span>{posting.location}</span>}
          <span>·</span>
          <span>{EMPLOYMENT_TYPE_LABEL[posting.employment_type] ?? posting.employment_type}</span>
          {posting.closes_at && (
            <>
              <span>·</span>
              <span>Applications close {posting.closes_at.slice(0, 10)}</span>
            </>
          )}
        </div>
      </div>

      {posting.description && (
        <div className="card">
          <h2 className="mb-2 font-semibold">About the role</h2>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
            {posting.description}
          </p>
        </div>
      )}

      {posting.requirements && (
        <div className="card">
          <h2 className="mb-2 font-semibold">What we&apos;re looking for</h2>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
            {posting.requirements}
          </p>
        </div>
      )}

      <div className="card border-brand-200">
        <h2 className="mb-1 font-semibold">Apply for this position</h2>
        <p className="mb-4 text-sm text-gray-500">
          Fill in your details and attach your CV (PDF or Word, max 5 MB).
        </p>
        <ApplyForm slug={params.slug} jobTitle={posting.title} />
      </div>
    </div>
  );
}
