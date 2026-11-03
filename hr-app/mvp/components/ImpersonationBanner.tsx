"use client";

import { useRouter } from "next/navigation";
import { Icon } from "./icons";

export default function ImpersonationBanner({ name }: { name: string }) {
  const router = useRouter();
  async function stop() {
    await fetch("/api/auth/impersonate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stop: true }),
    });
    router.refresh();
  }
  return (
    <div className="flex items-center justify-center gap-3 bg-yellow-400 px-4 py-1.5 text-sm font-medium text-yellow-950 print:hidden">
      <span className="flex items-center gap-1.5"><Icon name="warning" size={16} /> Impersonating {name} — all actions are audited</span>
      <button onClick={stop} className="rounded-md bg-yellow-950/10 px-2 py-0.5 text-xs font-semibold hover:bg-yellow-950/20">
        Stop
      </button>
    </div>
  );
}
