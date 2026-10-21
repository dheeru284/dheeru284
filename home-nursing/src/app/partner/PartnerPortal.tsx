"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, rupees } from "@/lib/client";
import { Alert, Empty, Field, StatusBadge, useAction } from "@/components/ui";

type Partner = null | { businessName: string; verificationStatus: string; properties: { id: string; name: string; city: string; verificationStatus: string; units: unknown[]; rates: { nightlyInPaise: number }[] }[] };
type Booking = { id: string; reference: string; property: string; unit: string; checkIn: string; checkOut: string; guests: number; status: string; totalInPaise: number; guest: { name: string | null; phone: string } };

export function PartnerPortal({ partner }: { partner: Partner }) {
  const r = useRouter();
  const act = useAction();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [adding, setAdding] = useState(false);
  const load = () => api<Booking[]>("/partners/me/bookings").then(setBookings).catch(() => undefined);
  useEffect(() => { if (partner) load(); }, [partner]);

  if (!partner)
    return (
      <form className="card mx-auto max-w-lg space-y-3" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api("/partners/me", { method: "PUT", body: { businessName: f.businessName, gstin: f.gstin || undefined } }); r.refresh(); }); }}>
        <h1 className="h1">Partner registration</h1>
        <Field label="Business name"><input name="businessName" className="input" required /></Field>
        <Field label="GSTIN (if registered)"><input name="gstin" className="input" /></Field>
        {act.error && <Alert>{act.error}</Alert>}
        <button className="btn" disabled={act.busy}>Continue</button>
      </form>
    );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="h1">{partner.businessName}</h1><button className="btn" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add property"}</button></div>
      {act.error && <Alert>{act.error}</Alert>}
      {adding && (
        <form className="card grid gap-3 sm:grid-cols-2" onSubmit={(e) => {
          e.preventDefault();
          const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
          const n = (k: string) => Number(f[k]);
          act.run(async () => {
            await api("/partners/me/properties", { body: { name: f.name, description: f.description, propertyType: f.type, address: f.address, city: f.city, state: f.state, pincode: f.pincode, latitude: n("lat"), longitude: n("lng"), bedrooms: n("bedrooms"), bathrooms: n("bathrooms"), maxGuests: n("maxGuests"), units: n("units"), minStayNights: n("minStay"), cancellationPolicy: f.cancellation, nightlyInPaise: n("nightly") * 100, monthlyInPaise: f.monthly ? n("monthly") * 100 : undefined, extendedStayDiscountPct: n("discount") || 0, depositInPaise: (n("deposit") || 0) * 100, amenities: f.amenities!.split(",").map((s) => s.trim()).filter(Boolean), accessibility: f.accessibility!.split(",").map((s) => s.trim()).filter(Boolean) } });
            setAdding(false); r.refresh();
          });
        }}>
          {[["name", "Property name"], ["type", "Type"], ["address", "Address"], ["city", "City"], ["state", "State"], ["pincode", "PIN code"], ["lat", "Latitude"], ["lng", "Longitude"], ["bedrooms", "Bedrooms"], ["bathrooms", "Bathrooms"], ["maxGuests", "Max guests"], ["units", "Identical units available"], ["minStay", "Minimum nights"], ["nightly", "₹ per night"], ["monthly", "₹ per 30 nights (optional)"], ["discount", "14+ night discount %"], ["deposit", "Deposit ₹"], ["amenities", "Amenities (comma-separated)"], ["accessibility", "Accessibility (e.g. lift, step_free_entry)"], ["cancellation", "Cancellation policy"]].map(([k, l]) =>
            k === "type" ? <Field key={k} label={l!}><select name="type" className="input"><option value="SERVICED_APARTMENT">Serviced apartment</option><option value="FURNISHED_APARTMENT">Furnished apartment</option><option value="GUEST_HOUSE">Guest house</option></select></Field>
              : <Field key={k} label={l!}><input name={k} className="input" required={!["monthly", "discount", "deposit", "amenities", "accessibility"].includes(k!)} defaultValue={k === "minStay" || k === "units" ? 1 : undefined} /></Field>,
          )}
          <Field label="Description"><textarea name="description" className="input" rows={2} required /></Field>
          <p className="text-xs text-ink-500 sm:col-span-2">New listings are reviewed before they appear in search.</p>
          <button className="btn sm:col-span-2" disabled={act.busy}>Submit listing</button>
        </form>
      )}
      <section className="space-y-2"><h2 className="h2">Properties</h2>{partner.properties.length ? partner.properties.map((p) => <div key={p.id} className="card flex justify-between"><span><b>{p.name}</b> · {p.city} · {p.units.length} unit(s) · {p.rates[0] ? rupees(p.rates[0].nightlyInPaise) + "/night" : ""}</span><StatusBadge status={p.verificationStatus} /></div>) : <Empty title="No properties yet" />}</section>
      <section className="space-y-2">
        <h2 className="h2">Booking requests and reservations</h2>
        {bookings.length ? bookings.map((b) => (
          <div key={b.id} className="card flex flex-wrap items-center justify-between gap-2">
            <span><b>{b.property}</b> · {b.unit} · {b.checkIn.slice(0, 10)} → {b.checkOut.slice(0, 10)} · {b.guests} guests<br /><span className="muted">{b.reference} · {b.guest.name ?? "Guest"} · {b.guest.phone} · {rupees(b.totalInPaise)}</span></span>
            <span className="flex items-center gap-2"><StatusBadge status={b.status} />{b.status === "REQUESTED" && <><button className="btn" onClick={() => act.run(async () => { await api(`/accommodation-bookings/${b.id}/respond`, { body: { decision: "CONFIRMED" } }); load(); })}>Confirm</button><button className="btn-secondary" onClick={() => act.run(async () => { await api(`/accommodation-bookings/${b.id}/respond`, { body: { decision: "DECLINED" } }); load(); })}>Decline</button></>}</span>
          </div>
        )) : <Empty title="No bookings yet" />}
      </section>
    </div>
  );
}
