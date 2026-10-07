import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import ScheduleOneOnOneForm from "../_components/ScheduleOneOnOneForm";
import { ONE_ON_ONE_STATUS_BADGE, fmtDateTime } from "../_lib/perf";

export const dynamic = "force-dynamic";

interface MeetingRow {
  id: number;
  manager_id: number;
  employee_id: number;
  scheduled_at: string;
  agenda: string | null;
  action_items: string;
  status: "scheduled" | "completed" | "cancelled";
  manager_name: string;
  employee_name: string;
}

const STATUS_LABEL: Record<string, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

function MeetingCard({ meeting, userId }: { meeting: MeetingRow; userId: number }) {
  const isManagerSide = meeting.manager_id === userId;
  const otherName = isManagerSide ? meeting.employee_name : meeting.manager_name;
  let openItems = 0;
  let totalItems = 0;
  try {
    const items = JSON.parse(meeting.action_items) as { done?: boolean }[];
    totalItems = items.length;
    openItems = items.filter((i) => !i.done).length;
  } catch {
    // ignore malformed JSON
  }

  return (
    <Link href={`/performance/one-on-ones/${meeting.id}`} className="card block transition-shadow hover:shadow-md">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium">
          {isManagerSide ? `With ${otherName}` : `With ${otherName} (your manager)`}
        </p>
        <span className={ONE_ON_ONE_STATUS_BADGE[meeting.status]}>{STATUS_LABEL[meeting.status]}</span>
      </div>
      <p className="mt-1 text-sm text-gray-500">{fmtDateTime(meeting.scheduled_at)}</p>
      {meeting.agenda && <p className="mt-2 line-clamp-2 text-sm text-gray-600">{meeting.agenda}</p>}
      {totalItems > 0 && (
        <p className="mt-2 text-xs text-gray-400">
          {openItems > 0 ? `${openItems} of ${totalItems} action items open` : `All ${totalItems} action items done`}
        </p>
      )}
    </Link>
  );
}

export default function OneOnOnesPage() {
  const db = getDb();
  const user = getCurrentUser();
  const userCanManage = canManage(user);
  const userIsHr = isHr(user);

  const meetings = db
    .prepare(
      `SELECT o.id, o.manager_id, o.employee_id, o.scheduled_at, o.agenda, o.action_items, o.status,
              m.first_name || ' ' || m.last_name AS manager_name,
              e.first_name || ' ' || e.last_name AS employee_name
       FROM one_on_ones o
       JOIN employees m ON m.id = o.manager_id
       JOIN employees e ON e.id = o.employee_id
       WHERE o.manager_id = ? OR o.employee_id = ?
       ORDER BY o.scheduled_at`
    )
    .all(user.id, user.id) as MeetingRow[];

  const upcoming = meetings.filter((m) => m.status === "scheduled");
  const past = meetings.filter((m) => m.status !== "scheduled").reverse();

  let employeeOptions: { id: number; name: string }[] = [];
  if (userIsHr) {
    employeeOptions = db
      .prepare(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status = 'active' AND id != ? ORDER BY first_name"
      )
      .all(user.id) as { id: number; name: string }[];
  } else if (userCanManage) {
    employeeOptions = db
      .prepare(
        "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status = 'active' AND manager_id = ? ORDER BY first_name"
      )
      .all(user.id) as { id: number; name: string }[];
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">1-on-1s</h1>
          <p className="text-sm text-gray-500">Your one-on-one meetings as manager or employee.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/performance" className="btn-secondary text-sm">← Performance overview</Link>
        </div>
      </div>

      {userCanManage && employeeOptions.length > 0 && <ScheduleOneOnOneForm employees={employeeOptions} />}

      <div>
        <h2 className="mb-3 font-semibold">Upcoming</h2>
        {upcoming.length === 0 ? (
          <p className="text-sm text-gray-500">No upcoming 1-on-1s.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {upcoming.map((m) => (
              <MeetingCard key={m.id} meeting={m} userId={user.id} />
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-3 font-semibold">Past</h2>
        {past.length === 0 ? (
          <p className="text-sm text-gray-500">No past 1-on-1s yet.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {past.map((m) => (
              <MeetingCard key={m.id} meeting={m} userId={user.id} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
