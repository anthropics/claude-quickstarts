import type { PayslipLine } from "@/lib/types";

export interface EmployeeEarningInput {
  name: string;
  taxable: number; // 1 = taxable, 0 = non-taxable
  amount: number;
}

export interface EmployeeDeductionInput {
  name: string;
  code: string;
  calc_type: "percentage" | "fixed";
  rate: number;
  pre_tax: number;
  statutory: number;
  override_amount: number | null;
}

/**
 * Informational payslip line (e.g. tax credits). Not an earning or deduction —
 * it does not move gross/net; it explains how a statutory amount was derived.
 */
export interface PayslipInfoLine {
  label: string;
  amount: number;
  type: "info";
}

export type EnginePayslipLine = PayslipLine | PayslipInfoLine;

export interface PayslipResult {
  gross: number;
  incomeTax: number;
  uif: number;
  /** Medical Scheme Fees Tax Credit actually applied against PAYE this month. */
  medicalTaxCredit: number;
  lines: EnginePayslipLine[];
  net: number;
  totalDeductions: number;
}

// SA Medical Scheme Fees Tax Credit, 2026 monthly rates (Rands).
const MTC_MAIN_MEMBER = 364; // main member
const MTC_FIRST_DEPENDANT = 364; // first dependant
const MTC_ADDITIONAL_DEPENDANT = 246; // each additional dependant

/**
 * Monthly Medical Scheme Fees Tax Credit for a member count.
 * members: 0 = no medical aid, 1 = main member only, 2 = +1 dependant, etc.
 */
export function medicalTaxCreditMonthly(members: number): number {
  if (!Number.isFinite(members) || members <= 0) return 0;
  if (members === 1) return MTC_MAIN_MEMBER;
  return MTC_MAIN_MEMBER + MTC_FIRST_DEPENDANT + (members - 2) * MTC_ADDITIONAL_DEPENDANT;
}

/**
 * Simplified ZA payroll engine.
 * Primary rebate: R17 235/year (2026).
 * UIF: 1% of gross, capped at R177.12/month.
 * PENSION: 7.5% of gross, pre-tax.
 * MEDICAL: fixed R1 800/month, post-tax.
 * PAYE: graduated on (taxableGross - preTaxDeductions) annualised.
 * Medical Scheme Fees Tax Credit: R364 main member + R364 first dependant +
 * R246 per additional dependant per month, applied against PAYE (floor 0),
 * only when the employee has an active MEDICAL deduction.
 */
export function calculatePayslip(
  earnings: EmployeeEarningInput[],
  deductions: EmployeeDeductionInput[],
  medicalAidMembers = 0
): PayslipResult {
  const gross = earnings.reduce((s, e) => s + e.amount, 0);
  const taxableGross = earnings.filter((e) => e.taxable).reduce((s, e) => s + e.amount, 0);

  // Pre-tax deductions (e.g. pension) reduce taxable income for PAYE
  let preTaxDedTotal = 0;
  const nonStatutoryLines: { label: string; amount: number; preTax: boolean }[] = [];
  for (const d of deductions) {
    if (d.statutory) continue; // PAYE and UIF are handled by engine
    const amt =
      d.override_amount !== null && d.override_amount !== undefined
        ? d.override_amount
        : d.calc_type === "percentage"
        ? gross * (d.rate / 100)
        : d.rate;
    const rounded = Math.round(amt * 100) / 100;
    nonStatutoryLines.push({ label: d.name, amount: rounded, preTax: !!d.pre_tax });
    if (d.pre_tax) preTaxDedTotal += rounded;
  }

  // UIF: 1% of gross, capped at R177.12/month
  const uif = Math.round(Math.min(gross * 0.01, 177.12) * 100) / 100;

  // PAYE: ZA 2026 brackets on annualised (taxable - pre-tax deductions)
  const taxableMonthly = taxableGross - preTaxDedTotal;
  const annual = taxableMonthly * 12;
  let annualTax = 0;
  if (annual <= 237100) annualTax = annual * 0.18;
  else if (annual <= 370500) annualTax = 42678 + (annual - 237100) * 0.26;
  else if (annual <= 512800) annualTax = 77362 + (annual - 370500) * 0.31;
  else if (annual <= 673000) annualTax = 121475 + (annual - 512800) * 0.36;
  else if (annual <= 857900) annualTax = 179147 + (annual - 673000) * 0.39;
  else if (annual <= 1817000) annualTax = 251258 + (annual - 857900) * 0.41;
  else annualTax = 644489 + (annual - 1817000) * 0.45;
  // Primary rebate 2026
  annualTax = Math.max(0, annualTax - 17235);
  const monthlyPayeBeforeCredit = annualTax / 12;

  // Medical Scheme Fees Tax Credit: only when the employee actually belongs to
  // a medical scheme (active MEDICAL deduction). Cannot push PAYE below 0.
  const hasMedicalDeduction = deductions.some((d) => d.code === "MEDICAL");
  const mtc = hasMedicalDeduction ? medicalTaxCreditMonthly(medicalAidMembers) : 0;
  const medicalTaxCredit = Math.round(Math.min(mtc, monthlyPayeBeforeCredit) * 100) / 100;
  const incomeTax = Math.round(Math.max(0, monthlyPayeBeforeCredit - mtc) * 100) / 100;

  // Build lines
  const lines: EnginePayslipLine[] = [];
  for (const e of earnings) {
    lines.push({ label: e.name, amount: e.amount, type: "earning" });
  }
  lines.push({ label: "PAYE Income Tax", amount: incomeTax, type: "deduction" });
  lines.push({ label: "UIF (Employee 1%)", amount: uif, type: "deduction" });
  for (const d of nonStatutoryLines) {
    lines.push({ label: d.label, amount: d.amount, type: "deduction" });
  }
  if (medicalTaxCredit > 0) {
    lines.push({
      label: "Medical Scheme Fees Tax Credit (reduces PAYE)",
      amount: medicalTaxCredit,
      type: "info",
    });
  }

  const totalNonStatutory = nonStatutoryLines.reduce((s, d) => s + d.amount, 0);
  const totalDeductions = Math.round((incomeTax + uif + totalNonStatutory) * 100) / 100;
  const net = Math.round((gross - totalDeductions) * 100) / 100;

  return { gross: Math.round(gross * 100) / 100, incomeTax, uif, medicalTaxCredit, lines, net, totalDeductions };
}
