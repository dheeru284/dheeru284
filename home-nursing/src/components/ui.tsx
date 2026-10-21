"use client";
import { useState, type ReactNode } from "react";

export function Alert({ kind = "error", children }: { kind?: "error" | "info" | "success" | "warn"; children: ReactNode }) {
  const cls = { error: "bg-alert-50 text-alert-600 border-red-200", info: "bg-brand-50 text-brand-900 border-brand-100", success: "bg-emerald-50 text-emerald-800 border-emerald-200", warn: "bg-amber-50 text-amber-900 border-amber-200" }[kind];
  return <div role={kind === "error" ? "alert" : "status"} className={`rounded-lg border px-4 py-3 text-sm ${cls}`}>{children}</div>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-500">{hint}</span>}
    </label>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone = /CANCEL|REJECT|DECLIN|NO_SHOW|SUSPEND|EXPIRED|REVOKED/.test(status) ? "bg-red-100 text-red-800" : /COMPLETE|CONFIRM|VERIFIED|APPROVED|SATISFIED/.test(status) ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900";
  return <span className={`badge ${tone}`}>{status.replaceAll("_", " ").toLowerCase()}</span>;
}

export function DemoBadge() {
  return <span className="badge bg-violet-100 text-violet-800" title="Fictional development data">Demo data — not a real person</span>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center">
      <p className="font-medium text-ink-700">{title}</p>
      {children && <div className="mt-2 text-sm text-ink-500">{children}</div>}
    </div>
  );
}

/** Wraps an async action with busy/error state. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      return undefined;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, run, setError };
}
