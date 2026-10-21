"use client";
import { useEffect, useState } from "react";
import { api, fmt, rupees } from "@/lib/client";
import { Alert, Field, StatusBadge, useAction } from "@/components/ui";

export function TimeOff() {
  const [list, setList] = useState<{ id: string; startsAt: string; endsAt: string; reason: string | null }[]>([]);
  const [warn, setWarn] = useState<string | null>(null);
  const act = useAction();
  const load = () => api<typeof list>("/nurses/me/time-off").then(setList).catch(() => undefined);
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps -- load once on mount
  return (
    <section className="card space-y-3">
      <h2 className="h2">Time off, breaks and holidays</h2>
      <form className="grid gap-2 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => {
        const r = await api<{ existingBookingsInPeriod: number }>("/nurses/me/time-off", { body: { startsAt: new Date(f.from!).toISOString(), endsAt: new Date(f.to!).toISOString(), reason: f.reason || undefined } });
        setWarn(r.existingBookingsInPeriod ? `You already have ${r.existingBookingsInPeriod} booking(s) in this period. They are not cancelled automatically — open each and cancel or keep it.` : null);
        load();
      }); }}>
        <Field label="From"><input name="from" type="datetime-local" className="input" required /></Field>
        <Field label="To"><input name="to" type="datetime-local" className="input" required /></Field>
        <Field label="Reason"><input name="reason" className="input" placeholder="Holiday" /></Field>
        <button className="btn-secondary self-end" disabled={act.busy}>Add</button>
      </form>
      {warn && <Alert kind="warn">{warn}</Alert>}
      {act.error && <Alert>{act.error}</Alert>}
      <ul className="text-sm">{list.map((x) => <li key={x.id} className="flex justify-between py-1"><span>{fmt(x.startsAt)} → {fmt(x.endsAt)} {x.reason && `· ${x.reason}`}</span><button className="underline" onClick={() => act.run(async () => { await api("/nurses/me/time-off", { method: "DELETE", body: { id: x.id } }); load(); })}>Remove</button></li>)}</ul>
    </section>
  );
}

export function Earnings() {
  const [d, setD] = useState<{ totals: { gross: number; commission: number; net: number; unpaidByPatient: number }; settlements: { id: string; periodStart: string; periodEnd: string; netInPaise: number; status: string }[] } | null>(null);
  useEffect(() => { api<typeof d>("/nurses/me/earnings").then(setD).catch(() => undefined); }, []);
  if (!d) return null;
  return (
    <section className="card space-y-2">
      <h2 className="h2">Earnings</h2>
      <p className="text-sm">Completed visits: gross {rupees(d.totals.gross)} − platform commission {rupees(d.totals.commission)} = <b>{rupees(d.totals.net)}</b>{d.totals.unpaidByPatient ? ` · ${rupees(d.totals.unpaidByPatient)} awaiting patient payment` : ""}</p>
      <h3 className="font-medium">Settlements</h3>
      {d.settlements.length ? <ul className="text-sm">{d.settlements.map((s) => <li key={s.id}>{s.periodStart.slice(0, 10)} → {s.periodEnd.slice(0, 10)}: {rupees(s.netInPaise)} <StatusBadge status={s.status} /></li>)}</ul> : <p className="muted">No settlements yet.</p>}
    </section>
  );
}
