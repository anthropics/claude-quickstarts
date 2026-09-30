import { getDb } from "./db";
import { notify, deliverOutbox } from "./notify";

/**
 * Scheduled jobs. runDueJobs() is idempotent — each job records its period key
 * in job_runs and refuses to re-run for the same period, so it is safe to call
 * from an interval timer, a cron hitting /api/admin/jobs, or manually.
 */
export interface JobResult {
  job: string;
  ran: boolean;
  detail: string;
}

export async function runDueJobs(now = new Date()): Promise<JobResult[]> {
  const results: JobResult[] = [];
  const today = now.toISOString().slice(0, 10);
  const month = today.slice(0, 7);
  const year = Number(today.slice(0, 4));

  results.push(runOnce("leave-accrual", month, () => accrueMonthlyLeave(month)));
  results.push(runOnce("leave-carry-over", String(year), () => carryOverLeave(year)));
  results.push(runOnce("probation-reminders", today, () => probationReminders(today)));
  results.push(runOnce("birthday-notices", today, () => birthdayNotices(today)));
  const outbox = await deliverOutbox();
  results.push({ job: "email-outbox", ran: true, detail: `sent=${outbox.sent} failed=${outbox.failed} skipped=${outbox.skipped}` });
  return results;
}

function runOnce(jobName: string, periodKey: string, fn: () => string): JobResult {
  const db = getDb();
  const done = db.prepare("SELECT 1 FROM job_runs WHERE job_name = ? AND period_key = ?").get(jobName, periodKey);
  if (done) return { job: jobName, ran: false, detail: `already ran for ${periodKey}` };
  const detail = fn();
  db.prepare("INSERT INTO job_runs (job_name, period_key, detail) VALUES (?, ?, ?)").run(jobName, periodKey, detail);
  return { job: jobName, ran: true, detail };
}

/**
 * Monthly accrual: for leave types with accrual_method='monthly', credit
 * entitlement/12 to every active employee for the given YYYY-MM period.
 */
function accrueMonthlyLeave(period: string): string {
  const db = getDb();
  const types = db.prepare("SELECT id, annual_entitlement_days FROM leave_types WHERE accrual_method = 'monthly' AND annual_entitlement_days > 0").all() as { id: number; annual_entitlement_days: number }[];
  if (types.length === 0) return "no monthly-accrual leave types";
  const employees = db.prepare("SELECT id FROM employees WHERE status = 'active'").all() as { id: number }[];
  const ins = db.prepare("INSERT OR IGNORE INTO leave_accruals (employee_id, leave_type_id, period, days) VALUES (?, ?, ?, ?)");
  let credited = 0;
  for (const t of types) {
    const monthly = Math.round((t.annual_entitlement_days / 12) * 100) / 100;
    for (const e of employees) credited += ins.run(e.id, t.id, period, monthly).changes;
  }
  return `credited ${credited} accrual rows for ${period}`;
}

/**
 * Annual carry-over: on entering a new year, carry unused balance from the
 * prior year up to each type's max_carry_over_days.
 */
function carryOverLeave(year: number): string {
  const db = getDb();
  const prior = year - 1;
  const types = db.prepare("SELECT id, annual_entitlement_days, max_carry_over_days FROM leave_types WHERE max_carry_over_days > 0").all() as { id: number; annual_entitlement_days: number; max_carry_over_days: number }[];
  if (types.length === 0) return "no carry-over-enabled leave types";
  const employees = db.prepare("SELECT id FROM employees WHERE status = 'active'").all() as { id: number }[];
  const ins = db.prepare("INSERT OR IGNORE INTO leave_carry_overs (employee_id, leave_type_id, year, days) VALUES (?, ?, ?, ?)");
  let rows = 0;
  for (const t of types) {
    for (const e of employees) {
      const taken = (db.prepare(
        "SELECT COALESCE(SUM(days),0) AS d FROM leave_requests WHERE employee_id = ? AND leave_type_id = ? AND status = 'approved' AND start_date >= ? AND start_date <= ?"
      ).get(e.id, t.id, `${prior}-01-01`, `${prior}-12-31`) as { d: number }).d;
      const unused = Math.max(0, t.annual_entitlement_days - taken);
      const carry = Math.min(unused, t.max_carry_over_days);
      if (carry > 0) rows += ins.run(e.id, t.id, year, carry).changes;
    }
  }
  return `carried over ${rows} balances into ${year}`;
}

/** Probation ending in exactly 30/14/7 days → notify manager + HR. */
function probationReminders(today: string): string {
  const db = getDb();
  let sent = 0;
  for (const days of [30, 14, 7]) {
    const target = addDays(today, days);
    const ending = db.prepare(
      "SELECT id, first_name, last_name, manager_id, probation_end_date FROM employees WHERE status = 'active' AND probation_end_date = ?"
    ).all(target) as { id: number; first_name: string; last_name: string; manager_id: number | null; probation_end_date: string }[];
    for (const e of ending) {
      const recipients = new Set<number>();
      if (e.manager_id) recipients.add(e.manager_id);
      for (const hr of db.prepare("SELECT id FROM employees WHERE role IN ('hr','admin') AND status = 'active'").all() as { id: number }[]) {
        recipients.add(hr.id);
      }
      for (const r of Array.from(recipients)) {
        notify({
          employeeId: r,
          type: "probation.ending",
          title: `${e.first_name} ${e.last_name}'s probation ends in ${days} days`,
          body: `Probation end date: ${e.probation_end_date}. Schedule the probation review.`,
          link: `/employees/${e.id}`,
        });
        sent++;
      }
    }
  }
  return `sent ${sent} probation reminders`;
}

/** Team birthday notices (in-app only). */
function birthdayNotices(today: string): string {
  const db = getDb();
  const mmdd = today.slice(5);
  const birthdays = db.prepare(
    "SELECT id, first_name, last_name FROM employees WHERE status = 'active' AND date_of_birth IS NOT NULL AND substr(date_of_birth, 6) = ?"
  ).all(mmdd) as { id: number; first_name: string; last_name: string }[];
  let sent = 0;
  for (const b of birthdays) {
    const team = db.prepare("SELECT id FROM employees WHERE status = 'active' AND id != ?").all(b.id) as { id: number }[];
    for (const t of team) {
      notify({
        employeeId: t.id,
        type: "birthday",
        title: `🎂 It's ${b.first_name} ${b.last_name}'s birthday today!`,
        email: false,
      });
      sent++;
    }
  }
  return `sent ${sent} birthday notices`;
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
