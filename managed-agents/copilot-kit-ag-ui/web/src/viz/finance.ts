/** Pure client-side finance math backing the interactive visuals. */

export interface PayoffResult {
  /** Remaining balance at the END of each month, starting with month 0 = principal. */
  balances: number[];
  months: number;
  totalInterest: number;
  /** False when the balance isn't cleared within the 50-year projection cap. */
  paysOff: boolean;
  /** False when the payment doesn't even cover interest — balance never falls. */
  coversInterest: boolean;
}

const MAX_MONTHS = 600;

export function payoffSchedule(
  principal: number,
  aprPercent: number,
  monthlyPayment: number,
): PayoffResult {
  const rate = aprPercent / 100 / 12;
  const balances: number[] = [principal];
  let balance = principal;
  let totalInterest = 0;

  for (let month = 1; month <= MAX_MONTHS; month++) {
    const interest = balance * rate;
    totalInterest += interest;
    balance = balance + interest - monthlyPayment;
    if (balance <= 0) {
      balances.push(0);
      return { balances, months: month, totalInterest, paysOff: true, coversInterest: true };
    }
    balances.push(balance);
    if (interest >= monthlyPayment) {
      // Payment doesn't cover interest — project a year of growth and stop.
      if (month >= 12) {
        return { balances, months: month, totalInterest, paysOff: false, coversInterest: false };
      }
    }
  }
  return { balances, months: MAX_MONTHS, totalInterest, paysOff: false, coversInterest: true };
}

/** Smallest whole-dollar payment that beats the first month's interest (the
 *  balance falls from there, though payoff can still exceed the 50-year cap). */
export function minimumViablePayment(principal: number, aprPercent: number): number {
  return Math.max(1, Math.ceil((principal * aprPercent) / 100 / 12) + 1);
}

export interface GrowthPoint {
  year: number;
  contributed: number;
  value: number;
}

export function growthSchedule(
  initialAmount: number,
  monthlyContribution: number,
  annualReturnPercent: number,
  years: number,
): GrowthPoint[] {
  const rate = annualReturnPercent / 100 / 12;
  const points: GrowthPoint[] = [{ year: 0, contributed: initialAmount, value: initialAmount }];
  let value = initialAmount;
  let contributed = initialAmount;
  const horizon = Math.min(Math.max(1, Math.round(years)), 50);

  for (let month = 1; month <= horizon * 12; month++) {
    value = value * (1 + rate) + monthlyContribution;
    contributed += monthlyContribution;
    if (month % 12 === 0) {
      points.push({ year: month / 12, contributed, value });
    }
  }
  return points;
}
