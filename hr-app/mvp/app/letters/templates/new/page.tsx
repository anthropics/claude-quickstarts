import Link from "next/link";
import { getCurrentUser, isHr } from "@/lib/session";
import TemplateForm from "../../_components/TemplateForm";

export const dynamic = "force-dynamic";

export default function NewTemplatePage() {
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

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href="/letters" className="text-sm font-medium text-brand-600 hover:underline">
          ← HR Letters
        </Link>
        <h1 className="mt-1 text-2xl font-bold">New letter template</h1>
      </div>
      <TemplateForm />
    </div>
  );
}
