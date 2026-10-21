"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, fmt, rupees } from "@/lib/client";
import { Alert, Field, StatusBadge, useAction } from "./ui";

type A = {
  viewer: "PATIENT" | "NURSE" | "ADMIN"; id: string; reference: string; status: string; startAt: string; endAt: string;
  service: { name: string; durationMinutes: number }; nurse: { id?: string; displayName: string; serviceArea?: string }; patient: { fullName: string; allergies?: string | null; medicalNotes?: string | null };
  address: { line1?: string; building?: string | null; landmark?: string | null; locality?: string | null; city: string; pincode?: string; latitude?: number; longitude?: number };
  travel: { minutes: number | null; distanceKm: number | null; source: string | null }; amountInPaise: number; paymentStatus: string; patientNotes: string | null;
  history: { id: string; toStatus: string; createdAt: string; note: string | null }[];
  visit: { notes: string | null; checklist: { itemKey: string; label: string; done: boolean }[] } | null;
};

const NURSE_NEXT: Record<string, { to: string; label: string }[]> = {
  AWAITING_NURSE_ACCEPTANCE: [{ to: "CONFIRMED", label: "Accept" }, { to: "CANCELLED", label: "Decline" }],
  CONFIRMED: [{ to: "NURSE_EN_ROUTE", label: "I'm on my way" }, { to: "CANCELLED", label: "Cancel" }],
  NURSE_EN_ROUTE: [{ to: "NURSE_ARRIVED", label: "I've arrived" }],
  NURSE_ARRIVED: [{ to: "IN_PROGRESS", label: "Start visit" }, { to: "NO_SHOW", label: "Patient not available" }],
  IN_PROGRESS: [{ to: "COMPLETED", label: "Complete visit" }],
};

type RazorpayResp = { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string };
/** Loads Razorpay Checkout; the result is verified server-side via /payments/confirm before anything is marked paid. */
async function openRazorpay(checkout: Record<string, unknown>, reference: string) {
  await new Promise<void>((res, rej) => {
    if ((window as unknown as { Razorpay?: unknown }).Razorpay) return res();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => res();
    s.onerror = () => rej(new Error("Could not load payment checkout"));
    document.body.appendChild(s);
  });
  await new Promise<void>((res, rej) => {
    const Rzp = (window as unknown as { Razorpay: new (o: unknown) => { open(): void } }).Razorpay;
    new Rzp({
      ...checkout, name: "HomeNurse India", description: `Visit ${reference}`,
      handler: (r: RazorpayResp) => api("/payments/confirm", { body: { providerOrderId: r.razorpay_order_id, providerPaymentId: r.razorpay_payment_id, signature: r.razorpay_signature } }).then(() => res(), rej),
      modal: { ondismiss: () => rej(new Error("Payment cancelled")) },
    }).open();
  });
}

export function AppointmentView({ a }: { a: A }) {
  const r = useRouter();
  const act = useAction();
  const [rs, setRs] = useState({ date: a.startAt.slice(0, 10), time: "10:00" });
  const [rating, setRating] = useState(5);
  const [notes, setNotes] = useState(a.visit?.notes ?? "");
  const go = (fn: () => Promise<unknown>) => act.run(async () => { await fn(); r.refresh(); });
  const transition = (to: string, note?: string) => go(() => api(`/appointments/${a.id}/transition`, { body: { to, note } }));
  const mapsUrl = a.address.latitude ? `https://www.google.com/maps/dir/?api=1&destination=${a.address.latitude},${a.address.longitude}` : null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        <div className="card space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2"><h1 className="h1">{a.service.name}</h1><StatusBadge status={a.status} /></div>
          <p className="muted">Ref {a.reference} · {fmt(a.startAt)} ({a.service.durationMinutes} min)</p>
          <p>Patient: <b>{a.patient.fullName}</b> · Nurse: <b>{a.nurse.displayName}</b> ({a.nurse.serviceArea})</p>
          <p className="text-sm">Address: {a.address.line1 ? `${a.address.line1}${a.address.building ? ", " + a.address.building : ""}, ${a.address.locality ?? ""}, ${a.address.city} ${a.address.pincode ?? ""}` : `${a.address.locality ?? ""} ${a.address.city} (full address shown after acceptance)`}{a.address.landmark && ` · Landmark: ${a.address.landmark}`}</p>
          {a.travel.minutes != null && <p className="text-sm">Estimated travel: ~{a.travel.minutes} min ({a.travel.source})</p>}
          {a.viewer === "NURSE" && mapsUrl && <a href={mapsUrl} target="_blank" rel="noreferrer" className="btn-secondary w-fit">Navigate</a>}
          {a.patient.allergies && <p className="text-sm"><b>Allergies:</b> {a.patient.allergies}</p>}
          {a.patient.medicalNotes && <p className="text-sm"><b>Care notes:</b> {a.patient.medicalNotes}</p>}
          {a.patientNotes && <p className="text-sm"><b>Booking notes:</b> {a.patientNotes}</p>}
        </div>

        {a.visit && (a.viewer === "NURSE" || a.viewer === "PATIENT") && (
          <div className="card space-y-3">
            <h2 className="h2">Visit checklist</h2>
            <p className="text-xs text-ink-500">Draft protocol — subject to clinical review.</p>
            <ul className="space-y-2">
              {a.visit.checklist.map((c) => (
                <li key={c.itemKey}><label className="flex items-center gap-2"><input type="checkbox" checked={c.done} disabled={a.viewer !== "NURSE" || a.status !== "IN_PROGRESS" || act.busy} onChange={(e) => go(() => api(`/visits/${a.id}/checklist`, { body: { itemKey: c.itemKey, done: e.target.checked } }))} /> {c.label}</label></li>
              ))}
            </ul>
            {a.viewer === "NURSE" ? (
              <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); go(() => api(`/visits/${a.id}/notes`, { body: { notes } })); }}>
                <Field label="Visit notes" hint="Record what was done. Do not record diagnoses you are not qualified to make."><textarea className="input" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
                <button className="btn-secondary" disabled={act.busy}>Save notes</button>
              </form>
            ) : a.visit.notes && <p className="text-sm whitespace-pre-wrap">{a.visit.notes}</p>}
          </div>
        )}

        <div className="card">
          <h2 className="h2 mb-2">History</h2>
          <ol className="space-y-1 text-sm">{a.history.map((h) => <li key={h.id}>{fmt(h.createdAt)} — {h.toStatus.replaceAll("_", " ").toLowerCase()}{h.note ? ` (${h.note})` : ""}</li>)}</ol>
        </div>
      </div>

      <aside className="space-y-4">
        {act.error && <Alert>{act.error}</Alert>}
        <div className="card space-y-2">
          <p className="text-2xl font-bold">{rupees(a.amountInPaise)}</p>
          <StatusBadge status={a.paymentStatus} />
          {a.viewer === "PATIENT" && a.paymentStatus === "UNPAID" && ["CONFIRMED", "COMPLETED"].includes(a.status) && (
            <button className="btn w-full" disabled={act.busy} onClick={() => go(async () => {
              const o = await api<{ providerOrderId: string; provider: string; checkout?: Record<string, unknown> }>("/payments/orders", { body: { appointmentId: a.id } });
              if (o.provider === "mock") {
                if (!confirm("Development payment adapter: no real money moves. Simulate a successful payment?")) return;
                await api("/payments/dev-simulate", { body: { providerOrderId: o.providerOrderId } });
                return;
              }
              await openRazorpay(o.checkout ?? {}, a.reference);
            })}>Pay now</button>
          )}
        </div>
        {a.viewer === "NURSE" && (
          <div className="card space-y-2">{(NURSE_NEXT[a.status] ?? []).map((n) => <button key={n.to} className={n.to === "CANCELLED" || n.to === "NO_SHOW" ? "btn-secondary w-full" : "btn w-full"} disabled={act.busy} onClick={() => transition(n.to)}>{n.label}</button>)}</div>
        )}
        {a.viewer === "PATIENT" && a.status === "AWAITING_AUTHORIZATION" && (
          <form className="card space-y-2" onSubmit={(e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            const file = fd.get("file") as File;
            go(async () => {
              const r = await api<{ upload: { url: string } }>(`/appointments/${a.id}/documents`, { body: { kind: fd.get("kind"), mimeType: file.type, sizeBytes: file.size } });
              const put = await fetch(r.upload.url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
              if (!put.ok) throw new Error("Upload failed");
            });
          }}>
            <h2 className="h2">Prescription required</h2>
            <p className="muted">Upload a valid prescription or clinician order. Our team checks it before the nurse is asked to confirm.</p>
            <select name="kind" className="input"><option value="PRESCRIPTION">Prescription</option><option value="CLINICIAN_ORDER">Clinician order</option></select>
            <input type="file" name="file" accept="application/pdf,image/jpeg,image/png" required className="text-sm" />
            <button className="btn w-full" disabled={act.busy}>Upload</button>
          </form>
        )}
        {a.viewer === "PATIENT" && (
          <div className="card space-y-2">
            <a className="btn-secondary w-full" href={`/patient/appointments/${a.id}/receipt`}>Receipt</a>
            {a.nurse.id && <button className="btn-secondary w-full" onClick={() => go(() => api("/favorites", { body: { nurseId: a.nurse.id } }))}>Save nurse to favourites</button>}
          </div>
        )}
        {a.viewer === "PATIENT" && ["AWAITING_NURSE_ACCEPTANCE", "CONFIRMED", "AWAITING_AUTHORIZATION"].includes(a.status) && (
          <div className="card space-y-3">
            <h2 className="h2">Change booking</h2>
            <div className="grid grid-cols-2 gap-2"><input type="date" className="input" value={rs.date} onChange={(e) => setRs({ ...rs, date: e.target.value })} /><input type="time" className="input" value={rs.time} onChange={(e) => setRs({ ...rs, time: e.target.value })} /></div>
            <button className="btn-secondary w-full" disabled={act.busy} onClick={() => act.run(async () => { const n = await api<{ id: string }>(`/appointments/${a.id}/reschedule`, { body: rs }); location.href = `/patient/appointments/${n.id}`; })}>Reschedule</button>
            <button className="btn-danger w-full" disabled={act.busy} onClick={() => confirm("Cancel this appointment? Late cancellations may incur a fee.") && transition("CANCELLED", "cancelled by patient")}>Cancel appointment</button>
          </div>
        )}
        {a.viewer === "PATIENT" && a.status === "COMPLETED" && (
          <div className="card space-y-2">
            <h2 className="h2">Rate this visit</h2>
            <select className="input" value={rating} onChange={(e) => setRating(Number(e.target.value))}>{[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{"★".repeat(n)}</option>)}</select>
            <button className="btn w-full" disabled={act.busy} onClick={() => go(() => api(`/appointments/${a.id}/review`, { body: { rating } }))}>Submit review</button>
          </div>
        )}
        {a.viewer !== "ADMIN" && (
          <button className="btn-secondary w-full" onClick={() => { const d = prompt("Describe the safety concern or complaint"); if (d && d.length >= 10) go(() => api("/support", { body: { type: "complaint", category: "appointment", severity: "SERIOUS", description: d, appointmentId: a.id } })); }}>Report a concern</button>
        )}
      </aside>
    </div>
  );
}
