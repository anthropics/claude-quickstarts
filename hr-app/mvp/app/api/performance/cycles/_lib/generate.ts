import type Database from "better-sqlite3";

/**
 * Generate self + manager review pairs for every active employee who has a
 * manager. Idempotent thanks to UNIQUE(cycle_id, employee_id, type) — safe to
 * call again for a cycle that already has (some) reviews.
 * Returns the number of reviews created.
 */
export function generateReviewPairs(db: Database.Database, cycleId: number): number {
  const employees = db
    .prepare("SELECT id, manager_id FROM employees WHERE status = 'active' AND manager_id IS NOT NULL")
    .all() as { id: number; manager_id: number }[];

  const insert = db.prepare(
    "INSERT OR IGNORE INTO reviews (cycle_id, employee_id, reviewer_id, type, status) VALUES (?, ?, ?, ?, 'pending')"
  );

  let created = 0;
  for (const e of employees) {
    created += insert.run(cycleId, e.id, e.id, "self").changes;
    created += insert.run(cycleId, e.id, e.manager_id, "manager").changes;
  }
  return created;
}
