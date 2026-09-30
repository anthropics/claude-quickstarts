import { getCurrentUser, isHr } from "@/lib/session";
import NewRunForm from "../_components/NewRunForm";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default function NewPayRunPage() {
  const user = getCurrentUser();

  if (!isHr(user)) {
    return (
      <div className="card max-w-md">
        <h1 className="text-lg font-semibold text-red-600">Access Denied</h1>
        <p className="mt-1 text-sm text-gray-600">Only HR administrators can create payroll runs.</p>
        <Link href="/payroll" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
          Back to Payroll →
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">New Pay Run</h1>
        <p className="text-sm text-gray-500">
          Define the pay period. Payslips will be calculated automatically for all active employees.
        </p>
      </div>
      <NewRunForm />
    </div>
  );
}
