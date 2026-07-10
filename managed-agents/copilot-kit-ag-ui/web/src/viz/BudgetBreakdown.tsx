/**
 * Budget bars: each category as a share of monthly income, with the
 * unallocated remainder (or overspend) called out.
 */
import React from 'react';
import { SERIES, INK, fmtUsd } from './theme';

export interface BudgetArgs {
  title: string;
  monthlyIncome: number;
  items: Array<{ category: string; amount: number }>;
}

const MAX_ROWS = 8;

export const BudgetBreakdown: React.FC<BudgetArgs> = ({ title, monthlyIncome, items }) => {
  const positive = (items ?? []).filter((i) => i && i.amount > 0);
  // The remainder must account for EVERY category, shown or folded — so
  // anything beyond the row cap folds into an explicit "Other" row.
  const shown = positive.slice(0, MAX_ROWS);
  const foldedAmount = positive.slice(MAX_ROWS).reduce((sum, i) => sum + i.amount, 0);
  const rows =
    foldedAmount > 0 ?
      [...shown, { category: `Other (${positive.length - MAX_ROWS} items)`, amount: foldedAmount }]
    : shown;
  const allocated = positive.reduce((sum, i) => sum + i.amount, 0);
  const remainder = monthlyIncome - allocated;
  const scale = Math.max(monthlyIncome, allocated, 1);

  return (
    <div className="viz-card">
      <h4>{title}</h4>
      <p className="viz-sub">{fmtUsd(monthlyIncome)}/mo income</p>
      <div className="viz-bars">
        {rows.map((row, i) => (
          <div className="viz-bar-row" key={`${row.category}-${i}`} title={`${row.category}: ${fmtUsd(row.amount)}`}>
            <span className="viz-bar-label">{row.category}</span>
            <div className="viz-bar-track">
              <div
                className="viz-bar-fill"
                style={{ width: `${(row.amount / scale) * 100}%`, background: SERIES.blue }}
              />
            </div>
            <span className="viz-bar-value">
              {fmtUsd(row.amount)}
              {monthlyIncome > 0 && <em> {Math.round((row.amount / monthlyIncome) * 100)}%</em>}
            </span>
          </div>
        ))}
        <div className="viz-bar-row" title={remainder >= 0 ? 'Unallocated' : 'Over budget'}>
          <span className="viz-bar-label">{remainder >= 0 ? 'Unallocated' : 'Over budget'}</span>
          <div className="viz-bar-track">
            <div
              className="viz-bar-fill"
              style={{
                width: `${(Math.abs(remainder) / scale) * 100}%`,
                background: remainder >= 0 ? SERIES.aqua : SERIES.yellow,
              }}
            />
          </div>
          <span className="viz-bar-value" style={{ color: remainder >= 0 ? INK.primary : SERIES.yellow }}>
            {fmtUsd(Math.abs(remainder))}
            {monthlyIncome > 0 && <em> {Math.round((Math.abs(remainder) / monthlyIncome) * 100)}%</em>}
          </span>
        </div>
      </div>
    </div>
  );
};
