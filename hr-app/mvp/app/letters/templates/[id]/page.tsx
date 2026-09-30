import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { LetterTemplate } from "../../_lib/data";
import TemplateForm from "../../_components/TemplateForm";

export const dynamic = "force-dynamic";

export default function EditTemplatePage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) notFound();

  const user = getCurrentUser();
  if (!isHr(user)) {
    return (
      <div className="card max-w-lg">
        <h1 className="font-semibold">Access denied</h1>
        <p className="mt-1 text-sm text-gray-500">Only HR and admins can manage letter templates.</p>
        <Link href="/" className="btn-secondary mt-4">
          Back to dashboard
        </Link>
      </div>
    );
  }

  const template = getDb().prepare("SELECT * FROM letter_templates WHERE id = ?").get(id) as
    | LetterTemplate
    | undefined;
  if (!template) notFound();

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href="/letters" className="text-sm font-medium text-brand-600 hover:underline">
          ← HR Letters
        </Link>
        <h1 className="mt-1 text-2xl font-bold">Edit template</h1>
        <p className="text-sm text-gray-500">{template.name}</p>
      </div>
      <TemplateForm template={template} />
    </div>
  );
}
