import type { Database } from "better-sqlite3";

const REQUIRED_TEXT = ["first_name", "last_name", "work_email", "employee_number", "job_title"] as const;
const OPTIONAL_TEXT = [
  "phone",
  "personal_email",
  "gender",
  "nationality",
  "address",
  "emergency_contact_name",
  "emergency_contact_phone",
] as const;

const EMPLOYMENT_TYPES = ["full_time", "part_time", "contract", "intern"];
const ROLES = ["admin", "hr", "manager", "employee"];
const STATUSES = ["active", "on_leave", "terminated"];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export type EmployeeData = Record<string, string | number | null>;

interface Options {
  /** PATCH semantics: only validate fields present in the payload. */
  partial: boolean;
  /** Id of the employee being edited (used to reject self-management). */
  selfId?: number;
}

/**
 * Validates an employee create/update payload. Returns the cleaned column map
 * on success or an error message on failure.
 */
export function validateEmployeePayload(
  db: Database,
  body: unknown,
  opts: Options
): { data: EmployeeData } | { error: string } {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return { error: "Request body must be a JSON object." };
  }
  const input = body as Record<string, unknown>;
  const data: EmployeeData = {};

  const has = (field: string) => !opts.partial || field in input;

  // Required text fields
  for (const field of REQUIRED_TEXT) {
    if (!has(field)) continue;
    const value = typeof input[field] === "string" ? (input[field] as string).trim() : "";
    if (!value) return { error: `${field.replace(/_/g, " ")} is required.` };
    data[field] = value;
  }
  if (typeof data.work_email === "string" && !data.work_email.includes("@")) {
    return { error: "work email must be a valid email address." };
  }

  // Required date
  if (has("start_date")) {
    const value = typeof input.start_date === "string" ? input.start_date.trim() : "";
    if (!DATE_RE.test(value)) return { error: "start date is required (YYYY-MM-DD)." };
    data.start_date = value;
  }

  // Enums
  const enums: [string, string[], boolean][] = [
    ["employment_type", EMPLOYMENT_TYPES, true],
    ["role", ROLES, true],
    ["status", STATUSES, opts.partial], // status is only editable, not part of create
  ];
  for (const [field, allowed, applicable] of enums) {
    if (!applicable || !has(field)) continue;
    const value = input[field];
    if (typeof value !== "string" || !allowed.includes(value)) {
      return { error: `${field.replace(/_/g, " ")} must be one of: ${allowed.join(", ")}.` };
    }
    data[field] = value;
  }

  // Optional dates
  for (const field of ["probation_end_date", "date_of_birth"]) {
    if (!(field in input)) continue;
    const value = input[field];
    if (value === null || value === "") {
      data[field] = null;
    } else if (typeof value === "string" && DATE_RE.test(value)) {
      data[field] = value;
    } else {
      return { error: `${field.replace(/_/g, " ")} must be a date (YYYY-MM-DD) or empty.` };
    }
  }

  // Optional text fields
  for (const field of OPTIONAL_TEXT) {
    if (!(field in input)) continue;
    const value = input[field];
    if (value === null || value === "") {
      data[field] = null;
    } else if (typeof value === "string") {
      data[field] = value.trim() || null;
    } else {
      return { error: `${field.replace(/_/g, " ")} must be a string or null.` };
    }
  }

  // Foreign keys
  if ("department_id" in input) {
    const value = input.department_id;
    if (value === null || value === "") {
      data.department_id = null;
    } else if (typeof value === "number" && Number.isInteger(value)) {
      const exists = db.prepare("SELECT 1 FROM departments WHERE id = ?").get(value);
      if (!exists) return { error: "Selected department does not exist." };
      data.department_id = value;
    } else {
      return { error: "department_id must be an integer or null." };
    }
  }
  if ("manager_id" in input) {
    const value = input.manager_id;
    if (value === null || value === "") {
      data.manager_id = null;
    } else if (typeof value === "number" && Number.isInteger(value)) {
      if (opts.selfId !== undefined && value === opts.selfId) {
        return { error: "An employee cannot be their own manager." };
      }
      const exists = db.prepare("SELECT 1 FROM employees WHERE id = ?").get(value);
      if (!exists) return { error: "Selected manager does not exist." };
      data.manager_id = value;
    } else {
      return { error: "manager_id must be an integer or null." };
    }
  }

  return { data };
}

/** Maps SQLite unique-constraint errors to a friendly message, or null if not one. */
export function uniqueConstraintMessage(err: unknown): string | null {
  if (err instanceof Error && err.message.includes("UNIQUE constraint failed")) {
    if (err.message.includes("employee_number")) return "That employee number is already in use.";
    if (err.message.includes("work_email")) return "That work email is already in use.";
    return "A unique field already has that value.";
  }
  return null;
}
