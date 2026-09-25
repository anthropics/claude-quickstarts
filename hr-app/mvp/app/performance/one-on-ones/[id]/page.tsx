import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { Employee, OneOnOne } from "@/lib/types";
import OneOnOneEditor from "../../_components/OneOnOneEditor";
import { ONE_ON_ONE_STATUS_BADGE, fmtDateTime } from "../../_lib/perf";

export const dynamic = "force-dynamic";

const STATUS_LABEL: Record<string, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

export default function OneOnOneDetailPage({ params }: { params: { id: string } }) {
  const db = getDb();
  const user = getCurrentUser();

  const id = Number(params.id);
  if (!Number.isInteger(id)) notFound();

  const meeting = db.prepare("SELECT * FROM one_on_ones WHERE id = ?").get(id) as OneOnOne | undefined;
  if (!meeting) notFound();

  if (meeting.manager_id !== user.id && meeting.employee_id !== user.id && !isHr(user)) {
    notFound();
  }

  const manager = db.prepare("SELECT * FROM employees WHERE id = ?").get(meeting.manager_id) as
    | Employee
    | undefined;
  const employee = db.prepare("SELECT * FROM employees WHERE id = ?").get(meeting.employee_id) as
    | Employee
    | undefined;
  if (!manager || !employee) notFound();

  let actionItems: { text: string; done: boolean }[] = [];
  try {
    const parsed = JSON.parse(meeting.action_items);
    if (Array.isArray(parsed)) {
      actionItems = parsed
        .filter((i): i is { text: string; done?: unknown } => typeof i === "object" && i !== null && typeof i.text === "string")
        .map((i) => ({ text: i.text, done: Boolean(i.done) }));
    }
  } catch {
    // ignore malformed JSON
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">
            1-on-1 — {manager.first_name} {manager.last_name} &amp; {employee.first_name} {employee.last_name}
          </h1>
          <p className="text-sm text-gray-500">{fmtDateTime(meeting.scheduled_at)}</p>
        </div>
        <Link href="/performance/one-on-ones" className="btn-secondary text-sm">← All 1-on-1s</Link>
      </div>

      <div className="card">
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <p className="label mb-0">Manager</p>
            <p className="text-sm font-medium">{manager.first_name} {manager.last_name}</p>
          </div>
          <div>
            <p className="label mb-0">Employee</p>
            <p className="text-sm font-medium">{employee.first_name} {employee.last_name}</p>
          </div>
          <div>
            <p className="label mb-0">Status</p>
            <span className={ONE_ON_ONE_STATUS_BADGE[meeting.status]}>{STATUS_LABEL[meeting.status]}</span>
          </div>
        </div>
      </div>

      <OneOnOneEditor
        meetingId={meeting.id}
        initialAgenda={meeting.agenda}
        initialNotes={meeting.notes}
        initialActionItems={actionItems}
        status={meeting.status}
      />
    </div>
  );
}
