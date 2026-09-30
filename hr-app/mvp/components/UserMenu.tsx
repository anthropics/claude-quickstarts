"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface Props {
  name: string;
  role: string;
  isAdmin: boolean;
  impersonating: boolean;
  employees: { id: number; name: string }[];
}

export default function UserMenu({ name, role, isAdmin, impersonating, employees }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  async function impersonate(id: string) {
    if (!id) return;
    await fetch("/api/auth/impersonate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employee_id: Number(id) }),
    });
    setOpen(false);
    router.refresh();
  }

  async function stopImpersonating() {
    await fetch("/api/auth/impersonate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stop: true }),
    });
    router.refresh();
  }

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-gray-100">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
          {name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
        </span>
        <span className="hidden sm:block">{name}</span>
        <span className="text-gray-400">▾</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-1 w-64 rounded-xl border border-gray-200 bg-white p-2 shadow-lg">
            <div className="px-3 py-2 text-xs text-gray-400">
              Signed in as <span className="font-medium text-gray-600">{name}</span> · <span className="capitalize">{role}</span>
            </div>
            <Link href="/account" onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2 text-sm hover:bg-gray-50">
              Account & password
            </Link>
            {impersonating && (
              <button onClick={stopImpersonating} className="block w-full rounded-lg px-3 py-2 text-left text-sm text-yellow-700 hover:bg-yellow-50">
                Stop impersonating
              </button>
            )}
            {isAdmin && !impersonating && (
              <div className="border-t border-gray-100 px-3 py-2">
                <label className="label">Impersonate (audited)</label>
                <select className="input text-xs" defaultValue="" onChange={(e) => impersonate(e.target.value)}>
                  <option value="" disabled>Select employee…</option>
                  {employees.map((e) => (
                    <option key={e.id} value={e.id}>{e.name}</option>
                  ))}
                </select>
              </div>
            )}
            <button onClick={logout} className="block w-full rounded-lg px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50">
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
