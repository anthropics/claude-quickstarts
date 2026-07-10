/** Scenario comparison: 2-5 options as labeled bars in one unit. */
import React from 'react';
import { SERIES, fmtUsd, fmtMonths } from './theme';

export interface ComparisonArgs {
  title: string;
  unit: 'dollars' | 'months' | 'percent';
  options: Array<{ label: string; value: number; note?: string }>;
}

const fmtValue = (value: number, unit: ComparisonArgs['unit']): string =>
  unit === 'dollars' ? fmtUsd(value)
  : unit === 'months' ? fmtMonths(Math.round(value))
  : `${value}%`;

export const Comparison: React.FC<ComparisonArgs> = ({ title, unit, options }) => {
  const rows = (options ?? []).filter((o) => o && Number.isFinite(o.value)).slice(0, 5);
  const scale = Math.max(1, ...rows.map((o) => Math.abs(o.value)));

  return (
    <div className="viz-card">
      <h4>{title}</h4>
      <div className="viz-bars">
        {rows.map((option) => (
          <div className="viz-bar-row" key={option.label} title={option.note ?? option.label}>
            <span className="viz-bar-label">{option.label}</span>
            <div className="viz-bar-track">
              <div
                className="viz-bar-fill"
                style={{ width: `${(Math.abs(option.value) / scale) * 100}%`, background: SERIES.blue }}
              />
            </div>
            <span className="viz-bar-value">{fmtValue(option.value, unit)}</span>
          </div>
        ))}
      </div>
      {rows.some((o) => o.note) && (
        <ul className="viz-notes">
          {rows
            .filter((o) => o.note)
            .map((o) => (
              <li key={o.label}>
                <b>{o.label}:</b> {o.note}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
};
