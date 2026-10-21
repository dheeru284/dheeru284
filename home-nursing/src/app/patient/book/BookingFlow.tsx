"use client";
import Link from "next/link";
import { useState } from "react";
import { api, rupees } from "@/lib/client";
import { Alert, DemoBadge, Empty, Field, useAction } from "@/components/ui";

type Match = {
  nurseId: string; displayName: string; gender: string; serviceArea: string; languages: string[]; yearsExperience: number; qualifications: string[];
  ratingAvg: number; ratingCount: number; completedVisits: number; priceInPaise: number; score: number; isDemo: boolean;
  travel: { minutes: number | null; distanceKm: number | null; source: string; trafficAware: boolean; simulated: boolean; unavailable: boolean };
};
type MatchResponse = { results: Match[]; appliedLimitMinutes: number; limitExpanded: boolean; emptyReason?: string; suggestions?: string[] };

const EMERGENCY = /chest pain|can'?t breathe|not breathing|unconscious|stroke|severe bleeding|seizure|suicid/i;

export function BookingFlow(props: { services: { id: string; name: string; durationMinutes: number; requiresPrescription: boolean }[]; patients: { id: string; fullName: string }[]; addresses: { id: string; label: string | null; line1: string; city: string }[]; initialService?: string }) {
  const tomorrow = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
  const [form, setForm] = useState({ serviceId: props.initialService ?? props.services[0]?.id ?? "", patientId: props.patients[0]?.id ?? "", addressId: props.addresses[0]?.id ?? "", date: tomorrow, time: "10:00", gender: "", languages: "", notes: "", repeat: false, everyDays: 1, count: 5 });
  const [matches, setMatches] = useState<MatchResponse | null>(null);
  const [booked, setBooked] = useState<{ id?: string; reference?: string; created?: string[]; skipped?: { startAt: string; reason: string }[] } | null>(null);
  const search = useAction();
  const book = useAction();
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value });
  const service = props.services.find((s) => s.id === form.serviceId);

  if (!props.patients.length || !props.addresses.length)
    return <Empty title="Add a patient and an address first"><Link href="/patient" className="text-brand-700 underline">Go to My care</Link></Empty>;

  if (booked)
    return (
      <div className="card space-y-3">
        <Alert kind="success">{booked.reference ? <>Request <b>{booked.reference}</b> sent. The nurse will confirm or decline; you&apos;ll be notified.</> : <>{booked.created?.length} visits requested.</>}</Alert>
        {!!booked.skipped?.length && <Alert kind="warn">{booked.skipped.length} dates were skipped because the nurse was not available: {booked.skipped.map((s) => new Date(s.startAt).toLocaleDateString("en-IN")).join(", ")}</Alert>}
        {service?.requiresPrescription && <Alert kind="info">This service needs a prescription or clinician order. Our team will review it before the nurse is asked to confirm.</Alert>}
        <div className="flex gap-3">{booked.id && <Link className="btn" href={`/patient/appointments/${booked.id}`}>View appointment</Link>}<Link className="btn-secondary" href="/patient">Back to My care</Link></div>
      </div>
    );

  const doSearch = (expand = false) =>
    search.run(async () => {
      setMatches(await api<MatchResponse>("/matching", { body: { serviceId: form.serviceId, addressId: form.addressId, date: form.date, time: form.time, genderPreference: form.gender || undefined, languages: form.languages ? form.languages.split(",").map((s) => s.trim()).filter(Boolean) : undefined, requestExpandedLimit: expand || undefined } }));
    });

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
      <form className="card h-fit space-y-4" onSubmit={(e) => { e.preventDefault(); doSearch(); }}>
        <Field label="Service"><select className="input" value={form.serviceId} onChange={set("serviceId")}>{props.services.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.durationMinutes} min)</option>)}</select></Field>
        <Field label="Patient"><select className="input" value={form.patientId} onChange={set("patientId")}>{props.patients.map((p) => <option key={p.id} value={p.id}>{p.fullName}</option>)}</select></Field>
        <Field label="Visit address"><select className="input" value={form.addressId} onChange={set("addressId")}>{props.addresses.map((a) => <option key={a.id} value={a.id}>{a.label ?? a.line1}, {a.city}</option>)}</select></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date"><input type="date" className="input" min={tomorrow} value={form.date} onChange={set("date")} required /></Field>
          <Field label="Start time (IST)"><input type="time" className="input" step={900} value={form.time} onChange={set("time")} required /></Field>
        </div>
        <Field label="Nurse gender preference"><select className="input" value={form.gender} onChange={set("gender")}><option value="">No preference</option><option value="FEMALE">Female</option><option value="MALE">Male</option></select></Field>
        <Field label="Preferred languages" hint="Comma-separated codes, e.g. hi, kn, ta"><input className="input" value={form.languages} onChange={set("languages")} /></Field>
        <Field label="Notes for the nurse (optional)" hint="Do not use this for emergencies."><textarea className="input" rows={2} value={form.notes} onChange={set("notes")} /></Field>
        {EMERGENCY.test(form.notes) && <Alert>This sounds like it may be an emergency. Call <a className="font-bold underline" href="tel:112">112</a> now or go to the nearest emergency department. This service cannot help in an emergency.</Alert>}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.repeat} onChange={set("repeat")} /> Recurring visits</label>
        {form.repeat && <div className="grid grid-cols-2 gap-3"><Field label="Every (days)"><input type="number" min={1} max={30} className="input" value={form.everyDays} onChange={set("everyDays")} /></Field><Field label="Number of visits"><input type="number" min={2} max={60} className="input" value={form.count} onChange={set("count")} /></Field></div>}
        {search.error && <Alert>{search.error}</Alert>}
        <button className="btn w-full" disabled={search.busy}>{search.busy ? "Searching…" : "Find available nurses"}</button>
      </form>

      <section aria-live="polite" className="space-y-4">
        {!matches && <Empty title="Choose a service, address and time to see eligible nurses." />}
        {matches && (
          <>
            <p className="muted">Showing verified nurses approved for this service, available at this time and within <b>{matches.appliedLimitMinutes} minutes</b> estimated road travel{matches.limitExpanded && " (expanded on request)"}.</p>
            {!matches.results.length && (
              <div className="card space-y-2">
                <p className="font-medium">{matches.emptyReason}</p>
                <ul className="muted">{matches.suggestions?.map((s) => <li key={s}>• {s}</li>)}</ul>
                {matches.suggestions?.some((s) => s.startsWith("Request an expanded")) && <button className="btn-secondary" onClick={() => doSearch(true)}>Search with expanded limit</button>}
              </div>
            )}
            {book.error && <Alert>{book.error}</Alert>}
            <ul className="space-y-3">
              {matches.results.map((m) => (
                <li key={m.nurseId} className="card flex flex-col gap-3 sm:flex-row sm:items-center">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-100 text-lg font-bold text-brand-700" aria-hidden>{m.displayName.split(" ").map((x) => x[0]).slice(-2).join("")}</div>
                  <div className="flex-1 space-y-1">
                    <p className="font-semibold">{m.displayName} {m.isDemo && <DemoBadge />}</p>
                    <p className="text-sm"><span className="badge bg-emerald-100 text-emerald-800">Registration verified</span> {m.qualifications.join(", ")} · {m.yearsExperience} yrs · {m.gender.toLowerCase()}</p>
                    <p className="muted">{m.serviceArea} · Speaks {m.languages.join(", ")} · {m.ratingCount ? `★ ${m.ratingAvg.toFixed(1)} (${m.ratingCount})` : "No reviews yet"} · {m.completedVisits} visits</p>
                    <p className="text-sm">
                      {m.travel.unavailable ? <span className="text-amber-800">Travel time unavailable — needs manual confirmation</span> : <>~<b>{m.travel.minutes} min</b> drive ({m.travel.distanceKm} km){m.travel.trafficAware ? " · traffic-aware for your slot" : ""}</>}
                      {m.travel.simulated && <span className="ml-2 badge bg-amber-100 text-amber-900">Simulated estimate (dev)</span>}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold">{rupees(m.priceInPaise)}</p>
                    <button className="btn mt-2" disabled={book.busy} onClick={() => book.run(async () => {
                      const body = { patientId: form.patientId, nurseId: m.nurseId, serviceId: form.serviceId, addressId: form.addressId, date: form.date, time: form.time, patientNotes: form.notes || undefined, ...(form.repeat ? { recurrence: { everyDays: Number(form.everyDays), count: Number(form.count) } } : {}) };
                      setBooked(await api("/appointments", { body }));
                    })}>Request visit</button>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}
