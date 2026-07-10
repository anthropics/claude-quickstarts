/**
 * Interactive debt payoff: balance-over-time lines for the agent's plan and a
 * draggable what-if payment, with payoff time and total interest stat tiles.
 */
import React, { useMemo, useState } from 'react';
import { payoffSchedule, minimumViablePayment, type PayoffResult } from './finance';
import { LineChart } from './LineChart';
import { SERIES, fmtUsd, fmtUsdCompact, fmtMonths } from './theme';

export interface PayoffArgs {
  title: string;
  principal: number;
  aprPercent: number;
  monthlyPayment: number;
  comparisonPayment?: number;
}

const payoffLabel = (r: PayoffResult): string =>
  r.paysOff ? fmtMonths(r.months)
  : r.coversInterest ? '50+ years'
  : 'never pays off';

export const PayoffTimeline: React.FC<PayoffArgs> = ({
  title,
  principal,
  aprPercent,
  monthlyPayment,
  comparisonPayment,
}) => {
  const minPay = minimumViablePayment(principal, aprPercent);
  const maxPay = Math.max(
    monthlyPayment * 3,
    comparisonPayment ?? 0,
    Math.ceil(principal / 6),
    minPay + 100,
  );
  // Clamp into the slider's range so the thumb position never lies.
  const [whatIf, setWhatIf] = useState(() =>
    Math.min(maxPay, Math.max(minPay, comparisonPayment ?? monthlyPayment)),
  );

  const plan = useMemo(
    () => payoffSchedule(principal, aprPercent, monthlyPayment),
    [principal, aprPercent, monthlyPayment],
  );
  const alt = useMemo(
    () => payoffSchedule(principal, aprPercent, whatIf),
    [principal, aprPercent, whatIf],
  );
  const showAlt = whatIf !== monthlyPayment;

  return (
    <div className="viz-card">
      <h4>{title}</h4>
      <p className="viz-sub">
        {fmtUsd(principal)} at {aprPercent}% APR
      </p>
      <div className="viz-stats">
        <div>
          <span className="viz-stat-label">Plan: {fmtUsd(monthlyPayment)}/mo</span>
          <span className="viz-stat-value" style={{ color: SERIES.blue }}>
            {payoffLabel(plan)}
          </span>
          <span className="viz-stat-note">{fmtUsd(plan.totalInterest)} interest</span>
        </div>
        {showAlt && (
          <div>
            <span className="viz-stat-label">What-if: {fmtUsd(whatIf)}/mo</span>
            <span className="viz-stat-value" style={{ color: SERIES.yellow }}>
              {payoffLabel(alt)}
            </span>
            <span className="viz-stat-note">
              {fmtUsd(alt.totalInterest)} interest
              {plan.paysOff && alt.paysOff && alt.totalInterest < plan.totalInterest ?
                ` (saves ${fmtUsd(plan.totalInterest - alt.totalInterest)})`
              : ''}
            </span>
          </div>
        )}
      </div>
      <LineChart
        series={[
          { label: `${fmtUsd(monthlyPayment)}/mo`, color: SERIES.blue, values: plan.balances, area: !showAlt },
          ...(showAlt ? [{ label: `${fmtUsd(whatIf)}/mo`, color: SERIES.yellow, values: alt.balances }] : []),
        ]}
        fmtX={(m) => (m % 12 === 0 ? `Yr ${m / 12}` : `${m}mo`)}
        fmtY={fmtUsdCompact}
      />
      <label className="viz-slider">
        What if I paid <b>{fmtUsd(whatIf)}</b>/month?
        <input
          type="range"
          min={minPay}
          max={maxPay}
          step={5}
          value={whatIf}
          onChange={(e) => setWhatIf(Number(e.target.value))}
        />
      </label>
    </div>
  );
};
