/** Pure, client-safe helpers for the Expense module (no DB imports). */

/** Format an amount as South African Rand: `R 1 234.56` (space thousands separator). */
export function formatRand(n: number): string {
  const sign = n < 0 ? "-" : "";
  const [int, dec] = Math.abs(n).toFixed(2).split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${sign}R ${grouped}.${dec}`;
}

/** ISO date string YYYY-MM-DD validation. */
export function isIsoDate(s: unknown): s is string {
  return typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s));
}

/** Badge class per claim status: pending=yellow, approved=green, rejected=red, reimbursed=blue. */
export function claimStatusBadgeClass(status: string): string {
  switch (status) {
    case "pending":
      return "badge-yellow";
    case "approved":
      return "badge-green";
    case "rejected":
      return "badge-red";
    case "reimbursed":
      return "badge-blue";
    default:
      return "badge-gray";
  }
}
