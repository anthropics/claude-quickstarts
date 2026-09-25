import { NextResponse } from "next/server";
import { getApiUser, isHr } from "@/lib/session";
import { runDueJobs } from "@/lib/jobs";
import { logAudit } from "@/lib/db";

/** Manual jobs trigger (HR/admin). The interval runner calls runDueJobs directly. */
export async function POST() {
  const user = getApiUser();
  if (!user || !isHr(user)) return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const results = await runDueJobs();
  logAudit(user.id, "jobs.run", "job_runs", null, JSON.stringify(results.filter((r) => r.ran).map((r) => r.job)));
  return NextResponse.json({ results });
}
