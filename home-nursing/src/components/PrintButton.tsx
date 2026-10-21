"use client";
export function PrintButton() {
  return <button className="btn-secondary print:hidden" onClick={() => window.print()}>Print / save PDF</button>;
}
