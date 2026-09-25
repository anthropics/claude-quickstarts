import type { Database } from "better-sqlite3";
import type { MergeData } from "./render";

export interface LetterTemplate {
  id: number;
  name: string;
  type: "appointment" | "confirmation" | "warning" | "increase" | "general";
  body_template: string;
  created_at: string;
}

export interface GeneratedLetter {
  id: number;
  employee_id: number;
  template_id: number | null;
  title: string;
  content: string;
  created_by: number | null;
  created_at: string;
}

export const TEMPLATE_TYPES = ["appointment", "confirmation", "warning", "increase", "general"] as const;

interface MergeSubjectRow {
  first_name: string;
  last_name: string;
  job_title: string;
  start_date: string;
  employee_number: string;
  department_name: string | null;
  manager_name: string | null;
}

/** Builds the merge data for a letter about `employeeId`, authored by `author`. */
export function mergeDataForEmployee(
  db: Database,
  employeeId: number,
  author: { first_name: string; last_name: string },
  reason?: string | null
): MergeData | null {
  const emp = db
    .prepare(
      `SELECT e.first_name, e.last_name, e.job_title, e.start_date, e.employee_number,
              d.name AS department_name,
              m.first_name || ' ' || m.last_name AS manager_name
       FROM employees e
       LEFT JOIN departments d ON d.id = e.department_id
       LEFT JOIN employees m ON m.id = e.manager_id
       WHERE e.id = ?`
    )
    .get(employeeId) as MergeSubjectRow | undefined;
  if (!emp) return null;

  return {
    first_name: emp.first_name,
    last_name: emp.last_name,
    job_title: emp.job_title,
    department: emp.department_name ?? "",
    start_date: emp.start_date,
    employee_number: emp.employee_number,
    manager_name: emp.manager_name ?? "",
    author_name: `${author.first_name} ${author.last_name}`,
    reason: reason ?? "",
  };
}
