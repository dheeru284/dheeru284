"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/client";
import { Alert, Field, useAction } from "@/components/ui";

export function Caregivers({ patients }: { patients: { id: string; fullName: string; mine: boolean }[] }) {
  const [links, setLinks] = useState<{ id: string; relation: string; canBook: boolean; canViewRecords: boolean; patient: { fullName: string }; caregiver: { fullName: string | null; phone: string } }[]>([]);
  const act = useAction();
  const load = () => api<typeof links>("/caregivers/list").then(setLinks).catch(() => undefined);
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps -- load once on mount
  const own = patients.filter((p) => p.mine);
  return (
    <div className="card space-y-3">
      <h2 className="h2">Family caregivers</h2>
      <p className="muted">Let another registered family member book visits for someone you care for. Access to visit records is a separate permission.</p>
      {links.map((l) => <div key={l.id} className="flex items-center justify-between text-sm"><span>{l.caregiver.fullName ?? l.caregiver.phone} ({l.relation}) → {l.patient.fullName} · {l.canBook ? "can book" : ""}{l.canViewRecords ? ", can view records" : ""}</span><button className="underline" onClick={() => act.run(async () => { await api("/caregivers/list", { method: "DELETE", body: { id: l.id } }); load(); })}>Remove</button></div>)}
      {own.length > 0 && (
        <form className="grid gap-2 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget); act.run(async () => { await api("/caregivers", { body: { patientId: f.get("patientId"), caregiverPhone: f.get("phone"), relation: f.get("relation"), canBook: true, canViewRecords: f.get("records") === "on" } }); (e.target as HTMLFormElement).reset(); load(); }); }}>
          <Field label="For"><select name="patientId" className="input">{own.map((p) => <option key={p.id} value={p.id}>{p.fullName}</option>)}</select></Field>
          <Field label="Caregiver's mobile (+91…)"><input name="phone" className="input" required /></Field>
          <Field label="Relation"><input name="relation" className="input" placeholder="daughter" required /></Field>
          <label className="flex items-center gap-2 self-end text-sm"><input type="checkbox" name="records" /> Can view visit records</label>
          <button className="btn-secondary sm:col-span-2" disabled={act.busy}>Add caregiver</button>
        </form>
      )}
      {act.error && <Alert>{act.error}</Alert>}
    </div>
  );
}

export function Favorites() {
  const [favs, setFavs] = useState<{ nurse: { id: string; displayName: string; ratingAvg: number; ratingCount: number; serviceAreas: { label: string }[] } }[]>([]);
  useEffect(() => { api<typeof favs>("/favorites").then(setFavs).catch(() => undefined); }, []);
  return (
    <div className="card space-y-2">
      <h2 className="h2">Favourite nurses</h2>
      {favs.length ? favs.map(({ nurse: n }) => <div key={n.id} className="flex justify-between text-sm"><Link className="text-brand-700 underline" href={`/nurses/${n.id}`}>{n.displayName}</Link><span className="muted">{n.serviceAreas[0]?.label} · {n.ratingCount ? `★ ${n.ratingAvg.toFixed(1)}` : "new"}</span></div>) : <p className="muted">Save a nurse from an appointment page.</p>}
    </div>
  );
}

export function StayActions({ id, status, paymentStatus, checkOut }: { id: string; status: string; paymentStatus: string; checkOut: string }) {
  const r = useRouter();
  const act = useAction();
  const [ext, setExt] = useState("");
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      {status === "CONFIRMED" && paymentStatus === "UNPAID" && <button className="btn" disabled={act.busy} onClick={() => act.run(async () => {
        const o = await api<{ providerOrderId: string; provider: string }>(`/accommodation-bookings/${id}/pay`, { method: "POST" });
        if (o.provider !== "mock") throw new Error("Live checkout opens from the payment provider; contact support if it does not.");
        if (!confirm("Development payment adapter: no real money moves. Simulate payment?")) return;
        await api("/payments/dev-simulate", { body: { providerOrderId: o.providerOrderId } });
        r.refresh();
      })}>Pay stay + deposit</button>}
      {["CONFIRMED", "CHECKED_IN"].includes(status) && <><input type="date" className="input w-40" min={checkOut} value={ext} onChange={(e) => setExt(e.target.value)} /><button className="btn-secondary" disabled={!ext || act.busy} onClick={() => act.run(async () => { await api(`/accommodation-bookings/${id}/extend`, { body: { checkOut: ext } }); r.refresh(); })}>Extend stay</button></>}
      {["REQUESTED", "CONFIRMED"].includes(status) && <button className="btn-secondary" disabled={act.busy} onClick={() => confirm("Cancel this stay? The property's cancellation policy applies.") && act.run(async () => { await api(`/accommodation-bookings/${id}/cancel`, { method: "POST" }); r.refresh(); })}>Cancel</button>}
      {act.error && <span className="text-sm text-alert-600">{act.error}</span>}
    </div>
  );
}
