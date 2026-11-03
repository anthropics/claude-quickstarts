import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import NewJobPostingForm from "@/app/recruitment/_components/NewJobPostingForm";

export const dynamic = "force-dynamic";

interface Department {
  id: number;
  name: string;
}

export default function NewJobPostingPage() {
  const user = getCurrentUser();
  if (!isHr(user)) redirect("/recruitment");

  const db = getDb();
  const departments = db
    .prepare("SELECT id, name FROM departments ORDER BY name")
    .all() as Department[];

  return (
    <div className="space-y-6">
      <div>
        <a href="/recruitment" className="text-sm text-brand-600 hover:underline">
          ← Recruitment
        </a>
        <h1 className="mt-1 text-2xl font-bold">New job posting</h1>
        <p className="text-sm text-gray-500">
          Fill in the details and save as a draft. You can publish it later.
        </p>
      </div>
      <div className="card">
        <NewJobPostingForm departments={departments} />
      </div>
    </div>
  );
}
