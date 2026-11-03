import { notFound, redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import EditJobPostingForm from "@/app/recruitment/_components/EditJobPostingForm";
import type { JobPosting } from "@/lib/types";

export const dynamic = "force-dynamic";

interface Department {
  id: number;
  name: string;
}

export default function EditJobPostingPage({ params }: { params: { id: string } }) {
  const user = getCurrentUser();
  if (!isHr(user)) redirect(`/recruitment/${params.id}`);

  const db = getDb();
  const id = Number(params.id);

  const posting = db
    .prepare("SELECT * FROM job_postings WHERE id = ?")
    .get(id) as JobPosting | undefined;

  if (!posting) notFound();

  const departments = db
    .prepare("SELECT id, name FROM departments ORDER BY name")
    .all() as Department[];

  return (
    <div className="space-y-6">
      <div>
        <a href={`/recruitment/${id}`} className="text-sm text-brand-600 hover:underline">
          ← Back to posting
        </a>
        <h1 className="mt-1 text-2xl font-bold">Edit: {posting.title}</h1>
      </div>
      <div className="card">
        <EditJobPostingForm posting={posting} departments={departments} />
      </div>
    </div>
  );
}
