import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import type { Application, Candidate, JobPosting } from "@/lib/types";

export const dynamic = "force-dynamic";

const COMPANY = "Acme (Pty) Ltd";

type TemplateKey = "received" | "interview" | "offer" | "rejection";

const TEMPLATES: Record<TemplateKey, (m: { first_name: string; job_title: string }) => { subject: string; body: string }> = {
  received: (m) => ({
    subject: `Your application for ${m.job_title} at ${COMPANY}`,
    body: `Dear ${m.first_name},

Thank you for applying for the ${m.job_title} position at ${COMPANY}. We have received your application and our recruitment team is reviewing it.

We will be in touch as soon as there is an update on your application.`,
  }),
  interview: (m) => ({
    subject: `Interview invitation — ${m.job_title} at ${COMPANY}`,
    body: `Dear ${m.first_name},

Thank you for your application for the ${m.job_title} position at ${COMPANY}. We were impressed with your profile and would like to invite you to an interview.

A member of our team will contact you shortly to arrange a suitable time.`,
  }),
  offer: (m) => ({
    subject: `Offer of employment — ${m.job_title} at ${COMPANY}`,
    body: `Dear ${m.first_name},

We are delighted to inform you that we would like to offer you the position of ${m.job_title} at ${COMPANY}.

The formal offer letter with full details of the package will follow. Please review it and let us know if you have any questions.`,
  }),
  rejection: (m) => ({
    subject: `Update on your application — ${m.job_title} at ${COMPANY}`,
    body: `Dear ${m.first_name},

Thank you for your interest in the ${m.job_title} position at ${COMPANY} and for the time you invested in the process.

After careful consideration we have decided not to move forward with your application on this occasion. We encourage you to apply for future openings that match your experience, and we wish you every success in your search.`,
  }),
};

/**
 * Sends a canned email to the candidate. Candidates are not employees, so
 * notify() does not apply — the outbox row is inserted directly and a
 * timestamped note is appended to the application.
 */
export async function POST(request: Request, { params }: { params: { id: string } }) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden. HR/admin only." }, { status: 403 });
  }

  const db = getDb();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "Invalid application id." }, { status: 400 });
  }

  const app = db.prepare("SELECT * FROM applications WHERE id = ?").get(id) as Application | undefined;
  if (!app) {
    return NextResponse.json({ error: "Application not found." }, { status: 404 });
  }
  const candidate = db.prepare("SELECT * FROM candidates WHERE id = ?").get(app.candidate_id) as Candidate | undefined;
  const posting = db.prepare("SELECT * FROM job_postings WHERE id = ?").get(app.job_posting_id) as JobPosting | undefined;
  if (!candidate || !posting) {
    return NextResponse.json({ error: "Candidate or job posting not found." }, { status: 404 });
  }

  let body: { template?: string; custom_note?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const template = body.template as TemplateKey;
  if (!template || !(template in TEMPLATES)) {
    return NextResponse.json(
      { error: "template must be one of: received, interview, offer, rejection." },
      { status: 400 }
    );
  }
  const customNote = typeof body.custom_note === "string" ? body.custom_note.trim() : "";

  const rendered = TEMPLATES[template]({ first_name: candidate.first_name, job_title: posting.title });
  let bodyText = rendered.body;
  if (customNote) bodyText += `\n\n${customNote}`;
  bodyText += `\n\nKind regards,\nThe ${COMPANY} Recruitment Team`;

  db.prepare("INSERT INTO email_outbox (to_email, subject, body_text) VALUES (?, ?, ?)").run(
    candidate.email,
    rendered.subject,
    bodyText
  );

  // Record on the application's notes with a timestamp.
  const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
  const noteLine = `[${stamp}] '${template}' email sent to ${candidate.email} by ${user.first_name} ${user.last_name}`;
  const newNotes = app.notes ? `${app.notes}\n\n${noteLine}` : noteLine;
  db.prepare("UPDATE applications SET notes = ?, updated_at = datetime('now') WHERE id = ?").run(newNotes, id);

  logAudit(user.id, "email.send", "application", id, `template '${template}' to ${candidate.email}`);

  return NextResponse.json({ ok: true }, { status: 201 });
}
