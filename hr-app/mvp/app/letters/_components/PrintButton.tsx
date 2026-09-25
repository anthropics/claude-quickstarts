"use client";

export default function PrintButton() {
  return (
    <button type="button" className="btn-secondary" onClick={() => window.print()}>
      Print
    </button>
  );
}
