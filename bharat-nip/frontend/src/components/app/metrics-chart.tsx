"use client";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { NarrativeMetrics } from "@/lib/narratives";

const SERIES = [
  { key: "momentum", label: "Momentum", color: "#d97706" },
  { key: "public_interest", label: "Public relevance", color: "#2563eb" },
  { key: "evidence_strength", label: "Evidence strength", color: "#059669" },
  { key: "uncertainty", label: "Uncertainty", color: "#6b7280" },
  { key: "coverage", label: "Response coverage", color: "#7c3aed" },
] as const;

export function MetricsChart({ series }: { series: NarrativeMetrics[] }) {
  if (series.length < 2) {
    return <p className="text-sm text-muted-foreground">The chart appears after the metrics have changed at least once.</p>;
  }
  const data = series.map((m) => ({ ...m, at: m.computed_at.slice(0, 16).replace("T", " ") }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="at" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
          <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(2) : String(v))} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {SERIES.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color} dot={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
