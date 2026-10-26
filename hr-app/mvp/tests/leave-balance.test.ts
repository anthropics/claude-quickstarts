import { describe, it, expect, beforeEach, afterEach } from "vitest";
import Database from "better-sqlite3";
import { computeLeaveDays, getBalance, workingDays } from "@/app/leave/_lib/leave";

// ── Half-day / working-day computation (pure) ────────────────────────────────

// 2026-07-06 is a Monday; no SA public holidays that week.
// 2026-06-16 (Youth Day, a Tuesday) is used for the holiday case.
const NO_HOLIDAYS = new Set<string>();
const YOUTH_DAY = new Set(["2026-06-16"]);

describe("workingDays", () => {
  it("counts Mon-Fri of a plain week", () => {
    expect(workingDays("2026-07-06", "2026-07-10", NO_HOLIDAYS)).toBe(5);
  });

  it("excludes weekends", () => {
    expect(workingDays("2026-07-04", "2026-07-05", NO_HOLIDAYS)).toBe(0); // Sat-Sun
  });

  it("excludes public holidays", () => {
    // Mon 15 Jun – Wed 17 Jun with Youth Day (Tue 16th) as a holiday
    expect(workingDays("2026-06-15", "2026-06-17", YOUTH_DAY)).toBe(2);
  });
});

describe("computeLeaveDays (half-day flags)", () => {
  it("single day, half day → 0.5", () => {
    expect(computeLeaveDays("2026-07-06", "2026-07-06", NO_HOLIDAYS, true, false)).toBe(0.5);
  });

  it("single day, no flags → 1", () => {
    expect(computeLeaveDays("2026-07-06", "2026-07-06", NO_HOLIDAYS, false, false)).toBe(1);
  });

  it("multi-day with both flags subtracts a full day", () => {
    // Mon-Fri = 5 working days, minus 0.5 + 0.5
    expect(computeLeaveDays("2026-07-06", "2026-07-10", NO_HOLIDAYS, true, true)).toBe(4);
  });

  it("weekend-spanning range with a holiday and both flags", () => {
    // Fri 12 Jun → Wed 17 Jun: working days are Fri 12, Mon 15, Wed 17
    // (weekend 13-14 and Youth Day Tue 16 excluded) = 3, minus 1 → 2
    expect(computeLeaveDays("2026-06-12", "2026-06-17", YOUTH_DAY, true, true)).toBe(2);
  });

  it("never drops below half a day", () => {
    expect(computeLeaveDays("2026-07-06", "2026-07-06", NO_HOLIDAYS, true, true)).toBe(0.5);
  });

  it("returns 0 for ranges with no working days", () => {
    expect(computeLeaveDays("2026-07-04", "2026-07-05", NO_HOLIDAYS, false, false)).toBe(0);
  });
});

// ── getBalance (in-memory DB) ────────────────────────────────────────────────

const SCHEMA = `
  CREATE TABLE leave_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    colour TEXT NOT NULL DEFAULT '#3b5bdb',
    annual_entitlement_days REAL NOT NULL DEFAULT 0,
    paid INTEGER NOT NULL DEFAULT 1,
    probation_restricted INTEGER NOT NULL DEFAULT 0,
    negative_balance_allowed INTEGER NOT NULL DEFAULT 0,
    accrual_method TEXT NOT NULL DEFAULT 'annual',
    max_carry_over_days REAL NOT NULL DEFAULT 0
  );
  CREATE TABLE leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    leave_type_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    days REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    start_half INTEGER NOT NULL DEFAULT 0,
    end_half INTEGER NOT NULL DEFAULT 0
  );
  CREATE TABLE leave_accruals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    leave_type_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    days REAL NOT NULL,
    UNIQUE(employee_id, leave_type_id, period)
  );
  CREATE TABLE leave_carry_overs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    leave_type_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    days REAL NOT NULL,
    UNIQUE(employee_id, leave_type_id, year)
  );
`;

describe("getBalance", () => {
  let db: Database.Database;
  const EMP = 1;

  beforeEach(() => {
    db = new Database(":memory:");
    db.exec(SCHEMA);
  });

  afterEach(() => {
    db.close();
  });

  it("monthly accrual type: entitled = sum of this year's accruals, plus carry-over", () => {
    db.prepare(
      "INSERT INTO leave_types (name, code, annual_entitlement_days, accrual_method, max_carry_over_days) VALUES ('Annual', 'ANNUAL', 18, 'monthly', 5)"
    ).run();
    const ins = db.prepare(
      "INSERT INTO leave_accruals (employee_id, leave_type_id, period, days) VALUES (?, 1, ?, ?)"
    );
    // Jan–Jul 2026 at 1.5/month = 10.5; a prior-year accrual must be ignored
    for (const m of ["01", "02", "03", "04", "05", "06", "07"]) ins.run(EMP, `2026-${m}`, 1.5);
    ins.run(EMP, "2025-12", 1.5);
    db.prepare("INSERT INTO leave_carry_overs (employee_id, leave_type_id, year, days) VALUES (?, 1, 2026, 4)").run(EMP);
    // 3 approved + 2 pending this year, 5 approved last year (ignored)
    db.prepare(
      "INSERT INTO leave_requests (employee_id, leave_type_id, start_date, end_date, days, status) VALUES (?, 1, '2026-03-02', '2026-03-04', 3, 'approved')"
    ).run(EMP);
    db.prepare(
      "INSERT INTO leave_requests (employee_id, leave_type_id, start_date, end_date, days, status) VALUES (?, 1, '2026-08-03', '2026-08-04', 2, 'pending')"
    ).run(EMP);
    db.prepare(
      "INSERT INTO leave_requests (employee_id, leave_type_id, start_date, end_date, days, status) VALUES (?, 1, '2025-06-02', '2025-06-06', 5, 'approved')"
    ).run(EMP);

    const b = getBalance(EMP, 1, 2026, db)!;
    expect(b.entitled).toBe(10.5);
    expect(b.carryOver).toBe(4);
    expect(b.taken).toBe(3);
    expect(b.pending).toBe(2);
    expect(b.available).toBe(10.5 + 4 - 3); // 11.5
  });

  it("annual type: entitled = annual entitlement, plus carry-over", () => {
    db.prepare(
      "INSERT INTO leave_types (name, code, annual_entitlement_days, accrual_method, max_carry_over_days) VALUES ('Annual', 'ANNUAL', 18, 'annual', 5)"
    ).run();
    db.prepare("INSERT INTO leave_carry_overs (employee_id, leave_type_id, year, days) VALUES (?, 1, 2026, 2)").run(EMP);
    db.prepare(
      "INSERT INTO leave_requests (employee_id, leave_type_id, start_date, end_date, days, status) VALUES (?, 1, '2026-02-02', '2026-02-06', 5, 'approved')"
    ).run(EMP);

    const b = getBalance(EMP, 1, 2026, db)!;
    expect(b.entitled).toBe(18);
    expect(b.carryOver).toBe(2);
    expect(b.taken).toBe(5);
    expect(b.available).toBe(15);
  });

  it("annual type ignores accrual rows; monthly type without accruals has 0 entitled", () => {
    db.prepare(
      "INSERT INTO leave_types (name, code, annual_entitlement_days, accrual_method) VALUES ('Annual', 'ANNUAL', 18, 'annual')"
    ).run();
    db.prepare(
      "INSERT INTO leave_types (name, code, annual_entitlement_days, accrual_method) VALUES ('Sick', 'SICK', 12, 'monthly')"
    ).run();
    db.prepare("INSERT INTO leave_accruals (employee_id, leave_type_id, period, days) VALUES (?, 1, '2026-01', 99)").run(EMP);

    expect(getBalance(EMP, 1, 2026, db)!.entitled).toBe(18);
    const sick = getBalance(EMP, 2, 2026, db)!;
    expect(sick.entitled).toBe(0);
    expect(sick.available).toBe(0);
  });

  it("returns null for an unknown leave type", () => {
    expect(getBalance(EMP, 99, 2026, db)).toBeNull();
  });

  it("half-day requests count fractionally against the balance", () => {
    db.prepare(
      "INSERT INTO leave_types (name, code, annual_entitlement_days, accrual_method) VALUES ('Annual', 'ANNUAL', 18, 'annual')"
    ).run();
    db.prepare(
      "INSERT INTO leave_requests (employee_id, leave_type_id, start_date, end_date, days, status, start_half) VALUES (?, 1, '2026-07-06', '2026-07-06', 0.5, 'approved', 1)"
    ).run(EMP);

    const b = getBalance(EMP, 1, 2026, db)!;
    expect(b.taken).toBe(0.5);
    expect(b.available).toBe(17.5);
  });
});
