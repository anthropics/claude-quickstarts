import { getCurrentUser } from "@/lib/session";
import ChangePasswordForm from "./ChangePasswordForm";

export const dynamic = "force-dynamic";

export default function AccountPage() {
  const user = getCurrentUser();
  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Account</h1>
        <p className="text-sm text-gray-500">{user.work_email} · <span className="capitalize">{user.role}</span></p>
      </div>
      <div className="card">
        <h2 className="mb-3 font-semibold">Change password</h2>
        <p className="mb-4 text-xs text-gray-500">
          Changing your password signs out every other session on this account.
        </p>
        <ChangePasswordForm />
      </div>
    </div>
  );
}
