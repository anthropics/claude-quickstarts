import { describe, it, expect } from "vitest";
import {
  calculatePayslip,
  medicalTaxCreditMonthly,
  type EmployeeEarningInput,
  type EmployeeDeductionInput,
} from "@/app/payroll/_lib/engine";

function basic(amount: number): EmployeeEarningInput[] {
  return [{ name: "Basic Salary", taxable: 1, amount }];
}

const PENSION: EmployeeDeductionInput = {
  name: "Pension Fund",
  code: "PENSION",
  calc_type: "percentage",
  rate: 7.5,
  pre_tax: 1,
  statutory: 0,
  override_amount: null,
};

const MEDICAL: EmployeeDeductionInput = {
  name: "Medical Aid",
  code: "MEDICAL",
  calc_type: "fixed",
  rate: 1800,
  pre_tax: 0,
  statutory: 0,
  override_amount: null,
};

describe("PAYE brackets (2026, primary rebate R17 235)", () => {
  it("R20 000/month (annual R240 000, 26% bracket)", () => {
    // 42678 + (240000 - 237100) * 0.26 = 43432; - 17235 = 26197; / 12 = 2183.0833
    const r = calculatePayslip(basic(20000), []);
    expect(r.incomeTax).toBe(2183.08);
    expect(r.gross).toBe(20000);
  });

  it("R50 000/month (annual R600 000, 36% bracket)", () => {
    // 121475 + (600000 - 512800) * 0.36 = 152867; - 17235 = 135632; / 12 = 11302.6667
    const r = calculatePayslip(basic(50000), []);
    expect(r.incomeTax).toBe(11302.67);
  });

  it("R100 000/month (annual R1 200 000, 41% bracket)", () => {
    // 251258 + (1200000 - 857900) * 0.41 = 391519; - 17235 = 374284; / 12 = 31190.3333
    const r = calculatePayslip(basic(100000), []);
    expect(r.incomeTax).toBe(31190.33);
  });
});

describe("rebate floor", () => {
  it("low salary below the tax threshold pays zero PAYE, never negative", () => {
    // annual 84000 * 0.18 = 15120 < rebate 17235
    const r = calculatePayslip(basic(7000), []);
    expect(r.incomeTax).toBe(0);
    expect(r.incomeTax).toBeGreaterThanOrEqual(0);
    expect(r.net).toBe(7000 - r.uif);
  });
});

describe("UIF", () => {
  it("is 1% of gross below the ceiling", () => {
    expect(calculatePayslip(basic(10000), []).uif).toBe(100);
  });

  it("caps at R177.12/month", () => {
    expect(calculatePayslip(basic(50000), []).uif).toBe(177.12);
    expect(calculatePayslip(basic(500000), []).uif).toBe(177.12);
  });
});

describe("pre-tax pension", () => {
  it("reduces PAYE relative to no pension", () => {
    const withPension = calculatePayslip(basic(30000), [PENSION]);
    const withoutPension = calculatePayslip(basic(30000), []);
    expect(withPension.incomeTax).toBeLessThan(withoutPension.incomeTax);
    // 7.5% of 30000 = 2250/month pre-tax, taxed at 26% marginal → 585/month less PAYE
    expect(withoutPension.incomeTax - withPension.incomeTax).toBeCloseTo(585, 2);
    expect(withPension.incomeTax).toBe(4198.08);
  });
});

describe("medical scheme fees tax credit (MTC)", () => {
  it("computes the 2026 monthly credit per member count", () => {
    expect(medicalTaxCreditMonthly(0)).toBe(0);
    expect(medicalTaxCreditMonthly(1)).toBe(364);
    expect(medicalTaxCreditMonthly(2)).toBe(728);
    expect(medicalTaxCreditMonthly(3)).toBe(974);
    expect(medicalTaxCreditMonthly(4)).toBe(1220);
  });

  it("reduces PAYE by the correct amount for 0/1/2/3 members", () => {
    // Base PAYE at R30 000/month with no credit: 4783.08
    const expected: Record<number, { paye: number; credit: number }> = {
      0: { paye: 4783.08, credit: 0 },
      1: { paye: 4419.08, credit: 364 },
      2: { paye: 4055.08, credit: 728 },
      3: { paye: 3809.08, credit: 974 },
    };
    for (const members of [0, 1, 2, 3]) {
      const r = calculatePayslip(basic(30000), [MEDICAL], members);
      expect(r.incomeTax).toBe(expected[members].paye);
      expect(r.medicalTaxCredit).toBe(expected[members].credit);
    }
  });

  it("applies no credit without an active MEDICAL deduction", () => {
    const r = calculatePayslip(basic(30000), [], 2);
    expect(r.incomeTax).toBe(4783.08);
    expect(r.medicalTaxCredit).toBe(0);
  });

  it("cannot push PAYE below zero", () => {
    // annual 144000 → PAYE before credit 723.75/month; credit for 3 members = 974
    const r = calculatePayslip(basic(12000), [MEDICAL], 3);
    expect(r.incomeTax).toBe(0);
    expect(r.incomeTax).toBeGreaterThanOrEqual(0);
    // only the usable portion of the credit is applied
    expect(r.medicalTaxCredit).toBe(723.75);
  });

  it("adds an info line for the applied credit", () => {
    const r = calculatePayslip(basic(30000), [MEDICAL], 2);
    const info = r.lines.filter((l) => l.type === "info");
    expect(info).toHaveLength(1);
    expect(info[0].amount).toBe(728);

    const noCredit = calculatePayslip(basic(30000), [MEDICAL], 0);
    expect(noCredit.lines.filter((l) => l.type === "info")).toHaveLength(0);
  });
});
