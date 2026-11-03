/**
 * Pure validation helpers for the public careers apply flow. No imports from
 * db/session so these stay unit-testable (tests/careers-validation.test.ts).
 */

export interface ApplyData {
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
}

export type ApplyValidation =
  | { ok: true; data: ApplyData }
  | { ok: false; error: string };

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function isValidEmail(email: string): boolean {
  return EMAIL_RE.test(email.trim());
}

/**
 * Validates the public application form fields. `website` is a honeypot —
 * humans never see it, so any value means the submission is automated.
 */
export function validateApplication(fields: {
  first_name?: unknown;
  last_name?: unknown;
  email?: unknown;
  phone?: unknown;
  website?: unknown;
}): ApplyValidation {
  // Honeypot: must be empty (or absent).
  if (typeof fields.website === "string" && fields.website.trim() !== "") {
    return { ok: false, error: "Submission rejected." };
  }

  const first_name = typeof fields.first_name === "string" ? fields.first_name.trim() : "";
  const last_name = typeof fields.last_name === "string" ? fields.last_name.trim() : "";
  const email = typeof fields.email === "string" ? fields.email.trim().toLowerCase() : "";
  const phone = typeof fields.phone === "string" && fields.phone.trim() ? fields.phone.trim() : null;

  if (!first_name) return { ok: false, error: "First name is required." };
  if (!last_name) return { ok: false, error: "Last name is required." };
  if (!email) return { ok: false, error: "Email is required." };
  if (!isValidEmail(email)) return { ok: false, error: "Please enter a valid email address." };

  return { ok: true, data: { first_name, last_name, email, phone } };
}

/**
 * Public slug for a job posting: kebab-cased title + "-<id>" so the slug is
 * always unique (e.g. "Senior Software Engineer" + 1 → senior-software-engineer-1).
 */
export function generateSlug(title: string, id: number): string {
  const base = title
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "") // strip diacritics left over from NFKD
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${base || "job"}-${id}`;
}
