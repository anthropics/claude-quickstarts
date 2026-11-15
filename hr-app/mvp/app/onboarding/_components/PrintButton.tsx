"use client";

export default function PrintButton() {
  return (
    <button className="btn-secondary" onClick={() => window.print()}>
      Print summary
    </button>
  );
}
