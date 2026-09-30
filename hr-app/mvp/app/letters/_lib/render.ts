/**
 * Pure merge-field renderer for HR letters.
 *
 * A template contains {{merge_fields}}; rendering is a plain string
 * substitution — no HTML parsing or evaluation happens here. Any HTML present
 * in employee data (or the template) survives as literal text; letter views
 * MUST display the rendered content through React text nodes (never
 * dangerouslySetInnerHTML) with `whitespace-pre-line` to preserve paragraph
 * breaks, so injected markup renders inert as visible characters.
 */

export const MERGE_FIELDS = [
  "first_name",
  "last_name",
  "job_title",
  "department",
  "start_date",
  "employee_number",
  "manager_name",
  "author_name",
  "reason",
] as const;

export type MergeField = (typeof MERGE_FIELDS)[number];

export type MergeData = Partial<Record<string, string | null | undefined>>;

const FIELD_RE = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

/**
 * Substitutes {{field}} placeholders with values from `data`.
 * Unknown or missing fields render as an empty string — a generated letter
 * must never leak raw {{placeholders}} to the recipient.
 */
export function renderTemplate(template: string, data: MergeData): string {
  return template.replace(FIELD_RE, (_match, field: string) => {
    const value = data[field];
    return value == null ? "" : String(value);
  });
}
