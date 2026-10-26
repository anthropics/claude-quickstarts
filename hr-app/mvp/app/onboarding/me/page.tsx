import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export default function MyOnboardingPage() {
  const db = getDb();
  const user = getCurrentUser();

  // Try to find most recent active instance, then any instance
  const instance = db
    .prepare(
      `SELECT id FROM onboarding_instances
       WHERE employee_id = ?
       ORDER BY completed_at IS NULL DESC, created_at DESC
       LIMIT 1`
    )
    .get(user.id) as { id: number } | undefined;

  if (instance) {
    redirect(`/onboarding/${instance.id}`);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Onboarding</h1>
        <p className="text-sm text-gray-500">Your personalised onboarding checklist.</p>
      </div>
      <div className="card py-12 text-center">
        <p className="text-lg font-medium text-gray-700">No active onboarding found</p>
        <p className="mt-1 text-sm text-gray-500">
          Your HR team will start an onboarding journey for you soon.
        </p>
      </div>
    </div>
  );
}
