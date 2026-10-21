"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/client";
import { Alert, Field, StatusBadge, useAction } from "@/components/ui";

type N = null | {
  displayName: string; gender: string; bio: string | null; languages: string[]; yearsExperience: number; status: string; isPaused: boolean;
  qualifications: { code: string; verificationStatus: string }[]; registrations: { id: string; councilName: string; registrationNumber: string; status: string }[];
  documents: { id: string; kind: string; status: string }[]; eligibilities: { serviceId: string; status: string }[];
  serviceAreas: { label: string; city: string; latitude: number; longitude: number; maxTravelMinutes: number | null }[];
  availability: { dayOfWeek: number; startMinute: number; endMinute: number }[];
};
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const mins = (s: string) => { const [h, m] = s.split(":").map(Number); return h! * 60 + m!; };

export function NurseOnboarding({ nurse, services }: { nurse: N; services: { id: string; name: string; requiredQualifications: string[]; basePriceInPaise: number }[] }) {
  const r = useRouter();
  const act = useAction();
  const [msg, setMsg] = useState<string | null>(null);
  const done = (m: string) => { setMsg(m); r.refresh(); };
  const area = nurse?.serviceAreas[0];
  const [week, setWeek] = useState(() => DAYS.map((_, d) => { const s = nurse?.availability.find((a) => a.dayOfWeek === d); return { on: !!s, start: hhmm(s?.startMinute ?? 540), end: hhmm(s?.endMinute ?? 1080) }; }));

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between"><h1 className="h1">Nurse profile</h1>{nurse && <StatusBadge status={nurse.status} />}</div>
      {msg && <Alert kind="success">{msg}</Alert>}
      {act.error && <Alert>{act.error}</Alert>}

      <form className="card space-y-3" onSubmit={(e) => {
        e.preventDefault();
        const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
        act.run(async () => {
          await api("/nurses/me", { method: "PUT", body: {
            displayName: f.displayName, gender: f.gender, bio: f.bio || undefined, languages: f.languages!.split(",").map((s) => s.trim()).filter(Boolean), yearsExperience: Number(f.years),
            qualifications: f.qual ? [{ code: f.qual, institution: f.institution || undefined }] : undefined,
            serviceArea: { label: f.areaLabel, city: f.city, latitude: Number(f.lat), longitude: Number(f.lng), maxTravelMinutes: f.maxTravel ? Number(f.maxTravel) : undefined },
          } });
          done("Profile saved.");
        });
      }}>
        <h2 className="h2">1. About you</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name shown to patients"><input name="displayName" className="input" defaultValue={nurse?.displayName} required /></Field>
          <Field label="Gender"><select name="gender" className="input" defaultValue={nurse?.gender ?? "FEMALE"}><option value="FEMALE">Female</option><option value="MALE">Male</option><option value="OTHER">Other</option></select></Field>
          <Field label="Languages" hint="e.g. en, hi, kn"><input name="languages" className="input" defaultValue={nurse?.languages.join(", ") ?? "en"} required /></Field>
          <Field label="Years of experience"><input name="years" type="number" min={0} className="input" defaultValue={nurse?.yearsExperience ?? 0} /></Field>
          <Field label="Highest nursing qualification"><select name="qual" className="input" defaultValue={nurse?.qualifications[0]?.code ?? "GNM"}><option value="ANM">ANM</option><option value="GNM">GNM</option><option value="BSC_NURSING">B.Sc Nursing</option><option value="POST_BASIC_BSC">Post Basic B.Sc</option><option value="MSC_NURSING">M.Sc Nursing</option></select></Field>
          <Field label="Institution"><input name="institution" className="input" /></Field>
        </div>
        <Field label="Short bio"><textarea name="bio" className="input" rows={2} defaultValue={nurse?.bio ?? ""} /></Field>
        <h3 className="font-semibold">Service area</h3>
        <p className="muted">Patients see only the area name. Your start location is used privately to estimate travel time.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Area name (public)" hint="e.g. Indiranagar, Bengaluru"><input name="areaLabel" className="input" defaultValue={area?.label} required /></Field>
          <Field label="City"><input name="city" className="input" defaultValue={area?.city} required /></Field>
          <Field label="Start latitude"><input name="lat" className="input" defaultValue={area?.latitude} required /></Field>
          <Field label="Start longitude"><input name="lng" className="input" defaultValue={area?.longitude} required /></Field>
          <Field label="Max travel I accept (minutes)" hint="Platform limit still applies"><input name="maxTravel" type="number" min={10} max={240} className="input" defaultValue={area?.maxTravelMinutes ?? ""} /></Field>
        </div>
        <button className="btn" disabled={act.busy}>Save profile</button>
      </form>

      {nurse && (
        <>
          <section className="card space-y-3">
            <h2 className="h2">2. Nursing council registration</h2>
            {nurse.registrations.map((x) => <p key={x.id} className="text-sm">{x.councilName} · {x.registrationNumber} <StatusBadge status={x.status} /></p>)}
            <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api("/nurses/me/registrations", { body: { councilName: f.council, state: f.state, registrationNumber: f.num, expiresOn: f.exp || undefined } }); done("Registration added — pending verification."); }); }}>
              <Field label="Council"><input name="council" className="input" placeholder="e.g. Karnataka State Nursing Council" required /></Field>
              <Field label="State"><input name="state" className="input" required /></Field>
              <Field label="Registration number"><input name="num" className="input" required /></Field>
              <Field label="Valid until (if any)"><input name="exp" type="date" className="input" /></Field>
              <button className="btn-secondary sm:col-span-2" disabled={act.busy}>Add registration</button>
            </form>
          </section>

          <section className="card space-y-3">
            <h2 className="h2">3. Documents</h2>
            <p className="muted">PDF, JPG or PNG up to 10 MB. Files go to private storage; only verification staff can open them.</p>
            <ul className="text-sm">{nurse.documents.map((d) => <li key={d.id}>{d.kind.replaceAll("_", " ").toLowerCase()} <StatusBadge status={d.status} /></li>)}</ul>
            <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => {
              e.preventDefault();
              const fd = new FormData(e.currentTarget);
              const file = fd.get("file") as File;
              act.run(async () => {
                const res = await api<{ upload: { url: string } }>("/nurse-credentials/uploads", { body: { kind: fd.get("kind"), mimeType: file.type, sizeBytes: file.size } });
                const put = await fetch(res.upload.url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
                if (!put.ok) throw new Error("Upload failed");
                done("Document uploaded — pending verification.");
              });
            }}>
              <Field label="Type"><select name="kind" className="input"><option value="REGISTRATION_CERT">Registration certificate</option><option value="QUALIFICATION_CERT">Qualification certificate</option><option value="ID_PROOF">Government ID</option><option value="PHOTO">Profile photo</option></select></Field>
              <input type="file" name="file" accept="application/pdf,image/jpeg,image/png" required className="text-sm" />
              <button className="btn-secondary" disabled={act.busy}>Upload</button>
            </form>
          </section>

          <section className="card space-y-3">
            <h2 className="h2">4. Services I offer</h2>
            <p className="muted">Each service is approved by our team against your verified qualifications.</p>
            <ul className="divide-y">{services.map((s) => {
              const e = nurse.eligibilities.find((x) => x.serviceId === s.id);
              return <li key={s.id} className="flex items-center justify-between py-2 text-sm"><span>{s.name}<br /><span className="text-xs text-ink-500">Requires: {s.requiredQualifications.join(" / ") || "—"}</span></span>{e ? <StatusBadge status={e.status} /> : <button className="btn-secondary" onClick={() => act.run(async () => { await api("/nurses/me/eligibility", { body: { serviceId: s.id } }); done("Requested."); })}>Request</button>}</li>;
            })}</ul>
          </section>

          <section className="card space-y-3">
            <h2 className="h2">5. Weekly availability (IST)</h2>
            {week.map((d, i) => (
              <div key={i} className="flex flex-wrap items-center gap-3 text-sm">
                <label className="flex w-20 items-center gap-2"><input type="checkbox" checked={d.on} onChange={(e) => setWeek(week.map((w, j) => (j === i ? { ...w, on: e.target.checked } : w)))} />{DAYS[i]}</label>
                <input type="time" className="input w-32" value={d.start} disabled={!d.on} onChange={(e) => setWeek(week.map((w, j) => (j === i ? { ...w, start: e.target.value } : w)))} />
                <span>to</span>
                <input type="time" className="input w-32" value={d.end} disabled={!d.on} onChange={(e) => setWeek(week.map((w, j) => (j === i ? { ...w, end: e.target.value } : w)))} />
              </div>
            ))}
            <button className="btn-secondary" disabled={act.busy} onClick={() => act.run(async () => { await api("/nurses/me/availability", { method: "PUT", body: { weekly: week.flatMap((d, i) => (d.on ? [{ dayOfWeek: i, startMinute: mins(d.start), endMinute: mins(d.end) }] : [])) } }); done("Availability saved."); })}>Save availability</button>
          </section>

          {["DRAFT", "REJECTED"].includes(nurse.status) && <button className="btn w-full" disabled={act.busy} onClick={() => act.run(async () => { await api("/nurses/me/submit", { method: "POST" }); done("Submitted for verification."); })}>Submit for verification</button>}
        </>
      )}
    </div>
  );
}
