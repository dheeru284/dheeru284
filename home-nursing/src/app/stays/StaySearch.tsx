"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, rupees } from "@/lib/client";
import { Alert, DemoBadge, Empty, Field, useAction } from "@/components/ui";

type Hospital = { id: string; name: string; city: string; address: string };
type Result = { id: string; name: string; propertyType: string; bedrooms: number; bathrooms: number; maxGuests: number; accessibility: string[]; amenities: string[]; isDemo: boolean; straightLineKm: number; travelToHospital: { minutes: number; distanceKm: number; simulated: boolean } | null; freeUnits: number; quote: { nights: number; totalInPaise: number; depositInPaise: number }; cancellationPolicy: string };

export function StaySearch() {
  const d = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
  const [q, setQ] = useState("");
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [form, setForm] = useState({ checkIn: d(7), checkOut: d(21), guests: 2, maxNightly: "", accessibility: "" });
  const [results, setResults] = useState<{ nights: number; results: Result[] } | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const act = useAction();
  const sp = useSearchParams();
  useEffect(() => {
    const id = sp.get("hospital");
    if (id) api<Hospital>(`/hospitals/${id}`).then(setHospital).catch(() => undefined);
  }, [sp]);

  useEffect(() => {
    const t = setTimeout(() => api<Hospital[]>(`/hospitals?q=${encodeURIComponent(q)}&limit=8`).then(setHospitals).catch(() => setHospitals([])), 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
      <form className="card h-fit space-y-3" onSubmit={(e) => { e.preventDefault(); if (!hospital) return act.setError("Choose a hospital"); act.run(async () => setResults(await api(`/accommodations/search?hospitalId=${hospital.id}&checkIn=${form.checkIn}&checkOut=${form.checkOut}&guests=${form.guests}${form.maxNightly ? `&maxNightly=${form.maxNightly}` : ""}${form.accessibility ? `&accessibility=${form.accessibility}` : ""}`))); }}>
        <Field label="Hospital">
          <input className="input" placeholder="Search by name or area" value={hospital ? hospital.name : q} onChange={(e) => { setHospital(null); setQ(e.target.value); }} />
        </Field>
        {!hospital && hospitals.length > 0 && <ul className="max-h-48 overflow-auto rounded-lg border">{hospitals.map((h) => <li key={h.id}><button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-brand-50" onClick={() => setHospital(h)}>{h.name}<br /><span className="text-xs text-ink-500">{h.address}, {h.city}</span></button></li>)}</ul>}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Check-in"><input type="date" className="input" value={form.checkIn} onChange={(e) => setForm({ ...form, checkIn: e.target.value })} /></Field>
          <Field label="Check-out"><input type="date" className="input" value={form.checkOut} onChange={(e) => setForm({ ...form, checkOut: e.target.value })} /></Field>
          <Field label="Guests"><input type="number" min={1} max={20} className="input" value={form.guests} onChange={(e) => setForm({ ...form, guests: Number(e.target.value) })} /></Field>
          <Field label="Max ₹/night"><input type="number" className="input" value={form.maxNightly} onChange={(e) => setForm({ ...form, maxNightly: e.target.value })} /></Field>
        </div>
        <Field label="Accessibility"><select className="input" value={form.accessibility} onChange={(e) => setForm({ ...form, accessibility: e.target.value })}><option value="">Any</option><option value="lift">Lift</option><option value="step_free_entry">Step-free entry</option><option value="wheelchair_bathroom">Wheelchair-accessible bathroom</option></select></Field>
        {act.error && <Alert>{act.error}</Alert>}
        <button className="btn w-full" disabled={act.busy}>Search stays</button>
      </form>
      <section className="space-y-3">
        {done && <Alert kind="success">{done}</Alert>}
        {!results ? <Empty title="Pick a hospital and dates to see nearby stays." /> : !results.results.length ? <Empty title="No verified stays available for these dates.">Try different dates or a higher budget.</Empty> : results.results.map((r) => (
          <article key={r.id} className="card space-y-2">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div><h2 className="font-semibold"><Link className="hover:underline" href={`/stays/${r.id}`}>{r.name}</Link> {r.isDemo && <DemoBadge />}</h2><p className="muted">{r.propertyType.replaceAll("_", " ").toLowerCase()} · {r.bedrooms} bed · {r.bathrooms} bath · up to {r.maxGuests} guests</p></div>
              <div className="text-right"><p className="text-lg font-bold">{rupees(r.quote.totalInPaise)}</p><p className="text-xs text-ink-500">{results.nights} nights{r.quote.depositInPaise ? ` + ${rupees(r.quote.depositInPaise)} refundable deposit` : ""}</p></div>
            </div>
            <p className="text-sm">{r.travelToHospital ? <>~{r.travelToHospital.minutes} min drive to hospital ({r.travelToHospital.distanceKm} km){r.travelToHospital.simulated && <span className="ml-2 badge bg-amber-100 text-amber-900">Simulated estimate (dev)</span>}</> : <>{r.straightLineKm} km straight-line (drive time unavailable)</>}</p>
            <p className="text-xs text-ink-500">{[...r.amenities, ...r.accessibility].join(" · ")} · {r.cancellationPolicy}</p>
            <button className="btn-secondary" disabled={act.busy} onClick={() => act.run(async () => {
              const b = await api<{ reference: string }>("/accommodation-bookings", { body: { propertyId: r.id, checkIn: form.checkIn, checkOut: form.checkOut, guests: form.guests, hospitalId: hospital?.id } });
              setDone(`Stay request ${b.reference} sent. The property will confirm shortly.`);
            }).catch(() => undefined)}>Request booking</button>
          </article>
        ))}
        <p className="text-xs text-ink-500">Requests require sign-in. Do not share medical details with property partners.</p>
      </section>
    </div>
  );
}
