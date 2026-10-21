"use client";
import { useEffect, useState } from "react";
import { api, fmt } from "@/lib/client";
import { Alert, Field, StatusBadge, useAction } from "@/components/ui";

export function AccountView() {
  const act = useAction();
  const [msg, setMsg] = useState<string | null>(null);
  const [reqs, setReqs] = useState<{ id: string; kind: string; status: string; createdAt: string }[]>([]);
  const [notes, setNotes] = useState<{ id: string; body: string; createdAt: string }[]>([]);
  const [me, setMe] = useState<{ fullName: string | null; email: string | null; phone: string } | null>(null);
  const [consents, setConsents] = useState<{ noticeVersion: string; consents: { id: string; purpose: string; grantedAt: string; withdrawnAt: string | null }[] } | null>(null);
  const load = () => {
    api<typeof reqs>("/privacy").then(setReqs).catch(() => undefined);
    api<typeof notes>("/notifications?limit=10").then(setNotes).catch(() => undefined);
    api<NonNullable<typeof me>>("/auth/me").then(setMe).catch(() => undefined);
    api<NonNullable<typeof consents>>("/consents").then(setConsents).catch(() => undefined);
  };
  useEffect(load, []);
  const privacy = (kind: string, confirmText?: string) => { if (confirmText && !confirm(confirmText)) return; const details = prompt("Optional details") ?? undefined; act.run(async () => { await api("/privacy", { body: { kind, details } }); setMsg("Request received. We will respond within the stated timeline."); load(); }); };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="h1">Account, privacy and support</h1>
      {msg && <Alert kind="success">{msg}</Alert>}
      {act.error && <Alert>{act.error}</Alert>}
      {me && (
        <form className="card grid gap-3 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api("/account", { method: "PATCH", body: { fullName: f.fullName || undefined, email: f.email || undefined } }); setMsg("Profile updated."); load(); }); }}>
          <h2 className="h2 sm:col-span-3">Profile</h2>
          <Field label="Mobile"><input className="input" value={me.phone} disabled /></Field>
          <Field label="Name"><input name="fullName" className="input" defaultValue={me.fullName ?? ""} /></Field>
          <Field label="Email (for receipts and updates)"><input name="email" type="email" className="input" defaultValue={me.email ?? ""} /></Field>
          <button className="btn-secondary sm:col-span-3 sm:w-fit" disabled={act.busy}>Save</button>
        </form>
      )}
      {consents && (
        <section className="card space-y-2">
          <h2 className="h2">Consents</h2>
          <p className="muted">Privacy notice version {consents.noticeVersion}. Withdrawing care consent may stop us from arranging visits.</p>
          <ul className="text-sm">{consents.consents.map((c) => <li key={c.id} className="flex justify-between py-1"><span>{c.purpose.replaceAll("_", " ")} · given {fmt(c.grantedAt)}{c.withdrawnAt && ` · withdrawn ${fmt(c.withdrawnAt)}`}</span>{!c.withdrawnAt && <button className="underline" onClick={() => confirm("Withdraw this consent?") && act.run(async () => { await api("/consents", { method: "DELETE", body: { consentId: c.id } }); load(); })}>withdraw</button>}</li>)}</ul>
          <div className="flex flex-wrap gap-2">{["marketing", "whatsapp_updates"].filter((p) => !consents.consents.some((c) => c.purpose === p && !c.withdrawnAt)).map((p) => <button key={p} className="btn-secondary" onClick={() => act.run(async () => { await api("/consents", { body: { purpose: p } }); load(); })}>Opt in: {p.replace("_", " ")}</button>)}</div>
        </section>
      )}
      <section className="card space-y-3">
        <h2 className="h2">Your data</h2>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" onClick={() => act.run(async () => { const d = await api("/privacy?export=1"); const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })); const a = document.createElement("a"); a.href = url; a.download = "my-data.json"; a.click(); })}>Download my data</button>
          <button className="btn-secondary" onClick={() => privacy("CORRECTION")}>Request correction</button>
          <button className="btn-secondary" onClick={() => privacy("CONSENT_WITHDRAWAL")}>Withdraw consent</button>
          <button className="btn-secondary" onClick={() => privacy("GRIEVANCE")}>Raise a grievance</button>
          <button className="btn-danger" onClick={() => privacy("DELETION", "Request deletion of your account? Active bookings must be completed or cancelled first; some records must be retained by law.")}>Delete my account</button>
        </div>
        {reqs.length > 0 && <ul className="text-sm">{reqs.map((r) => <li key={r.id}>{r.kind} · {fmt(r.createdAt)} <StatusBadge status={r.status} /></li>)}</ul>}
      </section>
      <section className="card space-y-3">
        <h2 className="h2">Contact support</h2>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api("/support", { body: f.type === "incident" ? { type: "incident", kind: "SAFETY", description: f.body } : f.type === "complaint" ? { type: "complaint", category: "general", description: f.body } : { type: "ticket", subject: f.subject || "Support request", body: f.body } }); setMsg("Thanks — our team will get back to you."); (e.target as HTMLFormElement).reset(); }); }}>
          <Field label="Type"><select name="type" className="input"><option value="ticket">Question / help</option><option value="complaint">Complaint</option><option value="incident">Report an unsafe situation</option></select></Field>
          <Field label="Subject"><input name="subject" className="input" /></Field>
          <Field label="Details" hint="For emergencies call 112."><textarea name="body" className="input" rows={4} minLength={10} required /></Field>
          <button className="btn" disabled={act.busy}>Send</button>
        </form>
      </section>
      <section className="card space-y-2"><h2 className="h2">Notifications</h2>{notes.length ? notes.map((n) => <p key={n.id} className="text-sm">{n.body} <span className="muted">· {fmt(n.createdAt)}</span></p>) : <p className="muted">No notifications.</p>}</section>
    </div>
  );
}
