import { getDb } from "@/lib/db";

/**
 * Total claimed by an employee in a category for a given month (YYYY-MM),
 * counting pending + approved + reimbursed claims (rejected/deleted don't
 * consume budget).
 */
export function monthCategoryTotal(employeeId: number, categoryId: number, month: string): number {
  const row = getDb()
    .prepare(
      `SELECT COALESCE(SUM(amount), 0) AS total
       FROM expense_claims
       WHERE employee_id = ? AND category_id = ?
         AND status IN ('pending', 'approved', 'reimbursed')
         AND strftime('%Y-%m', expense_date) = ?`
    )
    .get(employeeId, categoryId, month) as { total: number };
  return row.total;
}
