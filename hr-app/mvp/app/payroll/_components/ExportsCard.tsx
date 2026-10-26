"use client";

import { useState } from "react";

interface Props {
  /** Tax years (year of the end of the SA tax year, e.g. 2026 = Mar 2025 – Feb 2026). */
  years: number[];
}

/**
 * HR-only exports panel: pick a tax year and download the IRP5-style annual
 * tax certificate CSV for it.
 */
export default function ExportsCard({ years }: Props) {
  const [year, setYear] = useState<number>(years[0]);

  return (
    <div className="card">
      <h2 className="font-semibold">Exports</h2>
      <p className="mt-1 text-sm text-gray-500">
        IRP5-style annual tax certificates (CSV) — one row per employee, aggregated over the SA tax
        year (1 March to end of February), with SARS codes 3601 (gross), 4102 (PAYE) and 4141 (UIF).
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label htmlFor="irp5-year" className="text-sm font-medium text-gray-700">
          Tax year
        </label>
        <select
          id="irp5-year"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {y - 1}/{y}
            </option>
          ))}
        </select>
        <a href={`/api/payroll/exports/irp5?year=${year}`} className="btn-secondary" download>
          Download IRP5 CSV
        </a>
      </div>
    </div>
  );
}
