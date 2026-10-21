"use client";
import { useEffect, useState } from "react";
import { api, rupees } from "@/lib/client";
import { Alert, Field, StatusBadge, useAction } from "@/components/ui";

type Cal = { units: { id: string; label: string; bookings: { id: string; reference: string; checkIn: string; checkOut: string; status: string }[] }[]; blackouts: { id: string; startDate: string; endDate: string; reason: string | null }[]; rates: { id: string; nightlyInPaise: number; monthlyInPaise: number | null; validFrom: string; validTo: string | null; depositInPaise: number; extendedStayDiscountPct: number }[] };
const iso = (d: Date) => d.toISOString().slice(0, 10);

export function PropertyManager({ propertyId }: { propertyId: string }) {
  const [cal, setCal] = useState<Cal | null>(null);
  const act = useAction();
  const from = new Date(), to = new Date(Date.now() + 60 * 86_400_000);
  const load = () => api<Cal>(`/partners/me/properties/${propertyId}/calendar?from=${iso(from)}&to=${iso(to)}`).then(setCal).catch((e) => act.setError(e.message));
  useEffect(() => { load(); }, [propertyId]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!cal) return <p className="muted">Loading…</p>;
  const days = Array.from({ length: 60 }, (_, i) => new Date(from.getTime() + i * 86_400_000));
  const state = (unitBookings: Cal["units"][0]["bookings"], d: Date) => {
    const s = iso(d);
    if (cal.blackouts.some((b) => b.startDate.slice(0, 10) <= s && s < b.endDate.slice(0, 10))) return "bg-slate-400";
    const b = unitBookings.find((x) => x.checkIn.slice(0, 10) <= s && s < x.checkOut.slice(0, 10));
    return b ? (b.status === "REQUESTED" ? "bg-amber-300" : "bg-brand-500") : "bg-emerald-100";
  };
  return (
    <div className="space-y-4 border-t pt-4">
      {act.error && <Alert>{act.error}</Alert>}
      <div>
        <h3 className="font-semibold">Next 60 days</h3>
        <p className="text-xs text-ink-500"><span className="inline-block h-2 w-2 bg-emerald-100" /> free · <span className="inline-block h-2 w-2 bg-amber-300" /> requested · <span className="inline-block h-2 w-2 bg-brand-500" /> booked · <span className="inline-block h-2 w-2 bg-slate-400" /> blocked</p>
        <div className="mt-2 overflow-x-auto">
          {cal.units.map((u) => <div key={u.id} className="flex items-center gap-px"><span className="w-16 shrink-0 text-xs">{u.label}</span>{days.map((d) => <span key={d.toISOString()} title={iso(d)} className={`h-5 w-3 shrink-0 ${state(u.bookings, d)}`} />)}</div>)}
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api(`/partners/me/properties/${propertyId}/blackouts`, { body: { startDate: f.s, endDate: f.e, reason: f.r || undefined } }); load(); }); }}>
          <h3 className="font-semibold">Block dates</h3>
          <div className="grid grid-cols-2 gap-2"><Field label="From"><input name="s" type="date" className="input" required /></Field><Field label="Until (exclusive)"><input name="e" type="date" className="input" required /></Field></div>
          <Field label="Reason"><input name="r" className="input" placeholder="Maintenance" /></Field>
          <button className="btn-secondary" disabled={act.busy}>Block</button>
          <ul className="text-sm">{cal.blackouts.map((b) => <li key={b.id}>{b.startDate.slice(0, 10)} → {b.endDate.slice(0, 10)} {b.reason} <button type="button" className="underline" onClick={() => act.run(async () => { await api(`/partners/me/properties/${propertyId}/blackouts`, { method: "DELETE", body: { blackoutId: b.id } }); load(); })}>remove</button></li>)}</ul>
        </form>
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api(`/partners/me/properties/${propertyId}/rates`, { body: { nightlyInPaise: Number(f.n) * 100, monthlyInPaise: f.m ? Number(f.m) * 100 : undefined, extendedStayDiscountPct: Number(f.d || 0), depositInPaise: Number(f.dep || 0) * 100, validFrom: f.from, validTo: f.to || undefined } }); load(); }); }}>
          <h3 className="font-semibold">Pricing</h3>
          <ul className="text-sm">{cal.rates.map((r) => <li key={r.id}>From {r.validFrom.slice(0, 10)}{r.validTo ? ` to ${r.validTo.slice(0, 10)}` : ""}: {rupees(r.nightlyInPaise)}/night{r.monthlyInPaise ? `, ${rupees(r.monthlyInPaise)}/30 nights` : ""}, {r.extendedStayDiscountPct}% 14+ nights, deposit {rupees(r.depositInPaise)}</li>)}</ul>
          <div className="grid grid-cols-2 gap-2">
            <Field label="₹/night"><input name="n" type="number" className="input" required /></Field><Field label="₹/30 nights"><input name="m" type="number" className="input" /></Field>
            <Field label="14+ night discount %"><input name="d" type="number" className="input" /></Field><Field label="Deposit ₹"><input name="dep" type="number" className="input" /></Field>
            <Field label="Valid from"><input name="from" type="date" className="input" required /></Field><Field label="Valid to"><input name="to" type="date" className="input" /></Field>
          </div>
          <button className="btn-secondary" disabled={act.busy}>Add rate period</button>
          <p className="text-xs text-ink-500">Existing bookings keep their quoted price.</p>
        </form>
      </div>
      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); const file = fd.get("file") as File; act.run(async () => {
        const r = await api<{ upload: { url: string } }>(`/partners/me/properties/${propertyId}/photos`, { body: { mimeType: file.type, sizeBytes: file.size, alt: String(fd.get("alt")) } });
        const put = await fetch(r.upload.url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
        if (!put.ok) throw new Error("Upload failed");
        (e.target as HTMLFormElement).reset();
      }); }}>
        <Field label="Photo description"><input name="alt" className="input" required /></Field>
        <input type="file" name="file" accept="image/jpeg,image/png,image/webp" required className="text-sm" />
        <button className="btn-secondary" disabled={act.busy}>Upload photo</button>
      </form>
    </div>
  );
}

export function StayStatusButtons({ id, status, onDone }: { id: string; status: string; onDone: () => void }) {
  const act = useAction();
  const go = (to: string, reason?: string) => act.run(async () => { await api(`/accommodation-bookings/${id}/partner-status`, { body: { to, reason } }); onDone(); });
  return (
    <span className="flex flex-wrap gap-2">
      {status === "CONFIRMED" && <button className="btn-secondary" onClick={() => go("CHECKED_IN")}>Check in</button>}
      {status === "CHECKED_IN" && <button className="btn-secondary" onClick={() => go("COMPLETED")}>Check out</button>}
      {status === "CONFIRMED" && <button className="btn-secondary" onClick={() => { const r = prompt("Reason for cancelling this confirmed stay"); if (r) go("CANCELLED", r); }}>Cancel</button>}
      {act.error && <span className="text-xs text-alert-600">{act.error}</span>}
      <StatusBadge status={status} />
    </span>
  );
}
