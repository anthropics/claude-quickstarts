"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function ChangePasswordForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setOk(false);
    const fd = new FormData(e.currentTarget);
    if (fd.get("new_password") !== fd.get("confirm_password")) {
      setError("New passwords do not match");
      return;
    }
    setLoading(true);
    const res = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: fd.get("current_password"),
        new_password: fd.get("new_password"),
      }),
    });
    setLoading(false);
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      setError(j.error ?? "Password change failed");
      return;
    }
    (e.target as HTMLFormElement).reset();
    setOk(true);
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="label">Current password</label>
        <input name="current_password" type="password" required autoComplete="current-password" className="input" />
      </div>
      <div>
        <label className="label">New password (min 10 characters)</label>
        <input name="new_password" type="password" required minLength={10} autoComplete="new-password" className="input" />
      </div>
      <div>
        <label className="label">Confirm new password</label>
        <input name="confirm_password" type="password" required minLength={10} autoComplete="new-password" className="input" />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {ok && <p className="text-sm text-green-600">Password updated.</p>}
      <button type="submit" disabled={loading} className="btn-primary">
        {loading ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}
