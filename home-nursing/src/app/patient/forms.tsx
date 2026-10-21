"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/client";
import { Alert, Field, useAction } from "@/components/ui";

export function AddPatientForm() {
  const [open, setOpen] = useState(false);
  const r = useRouter();
  const { busy, error, run } = useAction();
  if (!open) return <button className="btn-secondary" onClick={() => setOpen(true)}>Add person</button>;
  return (
    <form className="space-y-3 border-t pt-3" onSubmit={(e) => {
      e.preventDefault();
      const f = new FormData(e.currentTarget);
      run(async () => {
        await api("/patients", { body: { fullName: f.get("fullName"), gender: f.get("gender"), dateOfBirth: f.get("dob") || undefined, allergies: f.get("allergies") || undefined, medicalNotes: f.get("notes") || undefined, consentToCareDataProcessing: f.get("consent") === "on" } });
        setOpen(false); r.refresh();
      });
    }}>
      <Field label="Full name"><input name="fullName" className="input" required /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Gender"><select name="gender" className="input"><option value="UNDISCLOSED">Prefer not to say</option><option value="FEMALE">Female</option><option value="MALE">Male</option><option value="OTHER">Other</option></select></Field>
        <Field label="Date of birth"><input name="dob" type="date" className="input" /></Field>
      </div>
      <Field label="Allergies (optional)"><input name="allergies" className="input" /></Field>
      <Field label="Notes for the nurse (optional)" hint="Shared only with a nurse after they accept a booking."><textarea name="notes" className="input" rows={2} /></Field>
      <label className="flex gap-2 text-sm"><input type="checkbox" name="consent" required /> I consent to this information being stored and shared with the assigned nurse to deliver care.</label>
      {error && <Alert>{error}</Alert>}
      <button className="btn" disabled={busy}>Save</button>
    </form>
  );
}

export function AddAddressForm() {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ lat: string; lng: string }>({ lat: "", lng: "" });
  const r = useRouter();
  const { busy, error, run, setError } = useAction();
  if (!open) return <button className="btn-secondary" onClick={() => setOpen(true)}>Add address</button>;
  return (
    <form className="space-y-3 border-t pt-3" onSubmit={(e) => {
      e.preventDefault();
      const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
      run(async () => {
        await api("/patients/addresses", { body: { label: f.label || undefined, line1: f.line1, building: f.building || undefined, landmark: f.landmark || undefined, locality: f.locality || undefined, city: f.city, state: f.state, pincode: f.pincode, latitude: Number(coords.lat), longitude: Number(coords.lng) } });
        setOpen(false); r.refresh();
      });
    }}>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Label"><input name="label" className="input" placeholder="Home" /></Field>
        <Field label="PIN code"><input name="pincode" className="input" inputMode="numeric" maxLength={6} required /></Field>
      </div>
      <Field label="Address line"><input name="line1" className="input" required /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Building / flat"><input name="building" className="input" /></Field>
        <Field label="Landmark"><input name="landmark" className="input" /></Field>
        <Field label="Locality"><input name="locality" className="input" /></Field>
        <Field label="City"><input name="city" className="input" required /></Field>
      </div>
      <Field label="State"><input name="state" className="input" required /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Latitude"><input className="input" value={coords.lat} onChange={(e) => setCoords({ ...coords, lat: e.target.value })} required /></Field>
        <Field label="Longitude"><input className="input" value={coords.lng} onChange={(e) => setCoords({ ...coords, lng: e.target.value })} required /></Field>
      </div>
      <button type="button" className="btn-secondary" onClick={() => navigator.geolocation?.getCurrentPosition((pos) => setCoords({ lat: pos.coords.latitude.toFixed(6), lng: pos.coords.longitude.toFixed(6) }), () => setError("Could not get your location. Enter coordinates or use the map search once configured."))}>Use my current location</button>
      <p className="text-xs text-ink-500">Map search and geocoding are enabled once a maps provider key is configured.</p>
      {error && <Alert>{error}</Alert>}
      <button className="btn" disabled={busy}>Save address</button>
    </form>
  );
}
