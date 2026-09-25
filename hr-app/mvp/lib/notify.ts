import { getDb } from "./db";

/**
 * Notification service. Every notify() writes an in-app notification and
 * queues an email in the outbox. Outbox delivery is attempted by the jobs
 * runner via SMTP when configured (SMTP_HOST etc.), otherwise rows are marked
 * 'skipped' — the in-app notification is always delivered.
 */
export interface NotifyInput {
  employeeId: number;
  type: string;           // e.g. leave.approved, expense.rejected, review.due
  title: string;
  body?: string;
  link?: string;
  email?: boolean;        // default true
}

export function notify(input: NotifyInput) {
  const db = getDb();
  db.prepare(
    "INSERT INTO notifications (employee_id, type, title, body, link) VALUES (?, ?, ?, ?, ?)"
  ).run(input.employeeId, input.type, input.title, input.body ?? null, input.link ?? null);

  if (input.email !== false) {
    const emp = db.prepare("SELECT work_email, first_name FROM employees WHERE id = ?").get(input.employeeId) as
      | { work_email: string; first_name: string }
      | undefined;
    if (emp) {
      db.prepare("INSERT INTO email_outbox (to_email, subject, body_text) VALUES (?, ?, ?)").run(
        emp.work_email,
        `[HRCore] ${input.title}`,
        `Hi ${emp.first_name},\n\n${input.body ?? input.title}\n\n${input.link ? `Open in HRCore: ${input.link}\n\n` : ""}— HRCore`
      );
    }
  }
}

export function notifyMany(employeeIds: number[], input: Omit<NotifyInput, "employeeId">) {
  for (const id of employeeIds) notify({ ...input, employeeId: id });
}

export function unreadCount(employeeId: number): number {
  return (
    getDb()
      .prepare("SELECT COUNT(*) AS n FROM notifications WHERE employee_id = ? AND read_at IS NULL")
      .get(employeeId) as { n: number }
  ).n;
}

/** Attempts SMTP delivery of pending outbox rows. No-op marking when SMTP is unconfigured. */
export async function deliverOutbox(limit = 50): Promise<{ sent: number; failed: number; skipped: number }> {
  const db = getDb();
  const pending = db.prepare("SELECT * FROM email_outbox WHERE status = 'pending' ORDER BY id LIMIT ?").all(limit) as {
    id: number; to_email: string; subject: string; body_text: string;
  }[];
  if (pending.length === 0) return { sent: 0, failed: 0, skipped: 0 };

  const host = process.env.SMTP_HOST;
  if (!host) {
    const mark = db.prepare("UPDATE email_outbox SET status = 'skipped', error = 'SMTP not configured' WHERE id = ?");
    for (const m of pending) mark.run(m.id);
    return { sent: 0, failed: 0, skipped: pending.length };
  }

  const nodemailer = await import("nodemailer");
  const transport = nodemailer.createTransport({
    host,
    port: Number(process.env.SMTP_PORT ?? 587),
    secure: process.env.SMTP_SECURE === "1",
    auth: process.env.SMTP_USER ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS } : undefined,
  });

  let sent = 0, failed = 0;
  for (const m of pending) {
    try {
      await transport.sendMail({
        from: process.env.SMTP_FROM ?? "hrcore@localhost",
        to: m.to_email,
        subject: m.subject,
        text: m.body_text,
      });
      db.prepare("UPDATE email_outbox SET status = 'sent', sent_at = datetime('now') WHERE id = ?").run(m.id);
      sent++;
    } catch (e) {
      db.prepare("UPDATE email_outbox SET status = 'failed', error = ? WHERE id = ?").run(String(e), m.id);
      failed++;
    }
  }
  return { sent, failed, skipped: 0 };
}
