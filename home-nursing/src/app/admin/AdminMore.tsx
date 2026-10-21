"use client";
import { useCallback, useEffect, useState } from "react";
import { api, fmt, rupees } from "@/lib/client";
import { Alert, Field, StatusBadge, useAction } from "@/components/ui";

function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const reload = useCallback(() => { api<T>(path).then(setData).catch((e) => setErr(e.message)); }, [path]);
  useEffect(reload, [reload]);
  return { data, err, reload };
}

export function Authorizations() {
  const { data, reload } = useLoad<{ id: string; reference: string; startAt: string; service: { name: string }; documents: { id: string; kind: string; verificationStatus: string }[] }[]>("/admin/authorizations");
  const act = useAction();
  return (
    <div className="space-y-3">
      <Alert kind="info">Check that the document is a genuine, current prescription or clinician order that matches the booked service and patient. Do not make clinical judgements; escalate doubts to the clinical lead.</Alert>
      {act.error && <Alert>{act.error}</Alert>}
      {data?.length === 0 && <p className="muted">No bookings awaiting authorization.</p>}
      {data?.map((a) => (
        <div key={a.id} className="card space-y-2">
          <p><b>{a.reference}</b> · {a.service.name} · {fmt(a.startAt)}</p>
          {!a.documents.length && <p className="muted">Waiting for the patient to upload.</p>}
          {a.documents.map((d) => (
            <div key={d.id} className="flex flex-wrap items-center gap-2 text-sm">
              {d.kind} <StatusBadge status={d.verificationStatus} />
              <button className="underline" onClick={() => act.run(async () => { const u = await api<{ url: string }>(`/admin/authorizations/${d.id}`); window.open(u.url, "_blank", "noopener"); })}>open</button>
              {d.verificationStatus === "PENDING" && <><button className="btn" onClick={() => act.run(async () => { await api(`/admin/authorizations/${d.id}`, { body: { decision: "VERIFIED" } }); reload(); })}>Accept</button><button className="btn-secondary" onClick={() => { const notes = prompt("Why is it not acceptable? (sent to staff log; patient sees a generic message)"); if (notes) act.run(async () => { await api(`/admin/authorizations/${d.id}`, { body: { decision: "REJECTED", notes } }); reload(); }); }}>Reject</button></>}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

const STATUSES = ["", "AWAITING_AUTHORIZATION", "AWAITING_NURSE_ACCEPTANCE", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "NO_SHOW", "UNDER_REVIEW"];
export function Bookings() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const { data, reload } = useLoad<{ id: string; reference: string; status: string; startAt: string; amountInPaise: number; paymentStatus: string; estTravelMinutes: number | null; travelEstimateSource: string | null; service: { name: string }; nurse: { displayName: string }; address: { city: string } }[]>(`/admin/appointments?limit=100${status ? `&status=${status}` : ""}${q ? `&q=${q}` : ""}`);
  const act = useAction();
  const move = (id: string, to: string) => { const note = prompt(`Reason for moving to ${to}`); if (note) act.run(async () => { await api(`/appointments/${id}/transition`, { body: { to, note } }); reload(); }); };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2"><select className="input w-60" value={status} onChange={(e) => setStatus(e.target.value)}>{STATUSES.map((s) => <option key={s} value={s}>{s || "All statuses"}</option>)}</select><input className="input w-48" placeholder="Reference" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      {act.error && <Alert>{act.error}</Alert>}
      <div className="card overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-2">Ref</th><th>When</th><th>Service</th><th>Nurse</th><th>City</th><th>Travel</th><th>Amount</th><th>Status</th><th /></tr></thead><tbody>
        {data?.map((a) => <tr key={a.id} className="border-b"><td className="py-1">{a.reference}</td><td>{fmt(a.startAt)}</td><td>{a.service.name}</td><td>{a.nurse.displayName}</td><td>{a.address.city}</td><td>{a.estTravelMinutes ?? "—"} min ({a.travelEstimateSource})</td><td>{rupees(a.amountInPaise)} · {a.paymentStatus.toLowerCase()}</td><td><StatusBadge status={a.status} /></td>
          <td className="space-x-2 whitespace-nowrap">{["AWAITING_NURSE_ACCEPTANCE", "CONFIRMED", "AWAITING_AUTHORIZATION", "UNDER_REVIEW"].includes(a.status) && <button className="underline" onClick={() => move(a.id, "CANCELLED")}>cancel</button>}{a.status === "COMPLETED" && <button className="underline" onClick={() => move(a.id, "UNDER_REVIEW")}>review</button>}{a.status === "UNDER_REVIEW" && <button className="underline" onClick={() => move(a.id, "COMPLETED")}>close review</button>}</td></tr>)}
      </tbody></table></div>
    </div>
  );
}

export function Users({ isAdmin }: { isAdmin: boolean }) {
  const [q, setQ] = useState("");
  const { data, reload } = useLoad<{ id: string; phone: string; fullName: string | null; status: string; createdAt: string; roles: { role: { key: string } }[] }[]>(`/admin/users?limit=100${q ? `&q=${encodeURIComponent(q)}` : ""}`);
  const act = useAction();
  return (
    <div className="space-y-3">
      <input className="input max-w-xs" placeholder="Search phone or name" value={q} onChange={(e) => setQ(e.target.value)} />
      {act.error && <Alert>{act.error}</Alert>}
      <div className="card overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-2">User</th><th>Roles</th><th>Joined</th><th>Status</th><th /></tr></thead><tbody>
        {data?.map((u) => <tr key={u.id} className="border-b"><td className="py-1">{u.fullName ?? "—"}<br /><span className="muted">{u.phone}</span></td><td>{u.roles.map((r) => r.role.key).join(", ")}</td><td>{fmt(u.createdAt)}</td><td><StatusBadge status={u.status} /></td>
          <td className="space-x-2 whitespace-nowrap">
            {u.status === "ACTIVE" ? <button className="underline" onClick={() => { const reason = prompt("Reason for suspension"); if (reason) act.run(async () => { await api(`/admin/users/${u.id}`, { body: { action: "status", status: "SUSPENDED", reason } }); reload(); }); }}>suspend</button> : u.status === "SUSPENDED" && <button className="underline" onClick={() => { const reason = prompt("Reason for reactivation"); if (reason) act.run(async () => { await api(`/admin/users/${u.id}`, { body: { action: "status", status: "ACTIVE", reason } }); reload(); }); }}>reactivate</button>}
            {isAdmin && <select className="rounded border text-xs" defaultValue="" onChange={(e) => { const role = e.target.value; e.target.value = ""; if (role && confirm(`Grant ${role}?`)) act.run(async () => { await api(`/admin/users/${u.id}`, { body: { action: "grant_role", role } }); reload(); }); }}><option value="">grant role…</option><option>SUPPORT_AGENT</option><option>COMPLIANCE_OFFICER</option><option>ADMIN</option></select>}
          </td></tr>)}
      </tbody></table></div>
    </div>
  );
}

type H = { id: string; name: string; address: string; city: string; state: string; pincode: string; verificationStatus: string; website: string | null };
export function Hospitals() {
  const { data, reload } = useLoad<H[]>("/hospitals?limit=100");
  const act = useAction();
  return (
    <div className="space-y-3">
      {act.error && <Alert>{act.error}</Alert>}
      <form className="card grid gap-2 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api("/hospitals", { body: { name: f.name, address: f.address, city: f.city, state: f.state, pincode: f.pincode, latitude: Number(f.lat), longitude: Number(f.lng), website: f.website || undefined, dataSource: f.source } }); (e.target as HTMLFormElement).reset(); reload(); }); }}>
        {[["name", "Name"], ["address", "Address"], ["city", "City"], ["state", "State"], ["pincode", "PIN"], ["lat", "Latitude"], ["lng", "Longitude"], ["website", "Website (optional)"], ["source", "Data source"]].map(([k, l]) => <Field key={k} label={l!}><input name={k} className="input" required={k !== "website"} /></Field>)}
        <button className="btn self-end">Add hospital</button>
      </form>
      {data?.map((h) => (
        <div key={h.id} className="card flex flex-wrap items-center justify-between gap-2 text-sm">
          <span><b>{h.name}</b> · {h.city} · <StatusBadge status={h.verificationStatus} /><br /><span className="muted">{h.address} {h.pincode} · id {h.id.slice(0, 8)}</span></span>
          <span className="space-x-2">
            {h.verificationStatus !== "VERIFIED" && <button className="underline" onClick={() => act.run(async () => { await api(`/hospitals/${h.id}`, { method: "PATCH", body: { verificationStatus: "VERIFIED" } }); reload(); })}>mark details verified</button>}
            <button className="underline" onClick={() => { const ref = prompt("Partnership agreement reference (leave empty to cancel)"); if (ref) act.run(async () => { await api(`/hospitals/${h.id}`, { method: "PATCH", body: { hasFormalPartnership: true, partnershipAgreementRef: ref } }); reload(); }); }}>record partnership</button>
            <select className="rounded border text-xs" defaultValue="" onChange={(e) => { const into = e.target.value; e.target.value = ""; if (into && confirm("Merge this duplicate into the selected hospital? It will be deactivated.")) act.run(async () => { await api(`/hospitals/${h.id}`, { method: "PATCH", body: { mergeInto: into } }); reload(); }); }}><option value="">merge into…</option>{data.filter((x) => x.id !== h.id).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
            <button className="underline" onClick={() => confirm("Deactivate?") && act.run(async () => { await api(`/hospitals/${h.id}`, { method: "PATCH", body: { isActive: false } }); reload(); })}>deactivate</button>
          </span>
        </div>
      ))}
    </div>
  );
}

export function Partners() {
  const { data, reload } = useLoad<{ id: string; businessName: string; gstin: string | null; verificationStatus: string; user: { phone: string }; _count: { properties: number } }[]>("/admin/partners");
  const act = useAction();
  return <div className="space-y-2">{act.error && <Alert>{act.error}</Alert>}{data?.map((p) => <div key={p.id} className="card flex flex-wrap items-center justify-between gap-2 text-sm"><span><b>{p.businessName}</b> · {p.user.phone} · GSTIN {p.gstin ?? "—"} · {p._count.properties} properties</span><span className="flex items-center gap-2"><StatusBadge status={p.verificationStatus} />{p.verificationStatus !== "VERIFIED" && <button className="btn" onClick={() => act.run(async () => { await api("/admin/partners", { body: { id: p.id, verificationStatus: "VERIFIED" } }); reload(); })}>Verify</button>}{p.verificationStatus !== "REJECTED" && <button className="btn-secondary" onClick={() => act.run(async () => { await api("/admin/partners", { body: { id: p.id, verificationStatus: "REJECTED" } }); reload(); })}>Reject</button>}</span></div>)}</div>;
}

export function Reviews() {
  const { data, reload } = useLoad<{ id: string; rating: number; comment: string | null; moderationStatus: string; createdAt: string; nurse: { displayName: string } }[]>("/admin/reviews?limit=100");
  const act = useAction();
  return <div className="space-y-2">{act.error && <Alert>{act.error}</Alert>}{data?.length === 0 && <p className="muted">No reviews yet.</p>}{data?.map((r) => <div key={r.id} className="card flex flex-wrap items-center justify-between gap-2 text-sm"><span>{"★".repeat(r.rating)} for {r.nurse.displayName} · {fmt(r.createdAt)}<br />{r.comment}</span><span className="flex gap-2"><StatusBadge status={r.moderationStatus} />{["VISIBLE", "HIDDEN", "FLAGGED"].filter((s) => s !== r.moderationStatus).map((s) => <button key={s} className="underline" onClick={() => act.run(async () => { await api("/admin/reviews", { method: "PATCH", body: { id: r.id, status: s } }); reload(); })}>{s.toLowerCase()}</button>)}</span></div>)}</div>;
}

export function Payments() {
  const rec = useLoad<{ id: string; provider: string; providerOrderId: string; providerPaymentId: string | null; amountInPaise: number; refundedInPaise: number; status: string; booking: string | null; createdAt: string; issues: string[] }[]>("/admin/reconciliation");
  const set = useLoad<{ id: string; partner: { businessName: string } | null; nurseId: string | null; periodStart: string; periodEnd: string; grossInPaise: number; commissionInPaise: number; netInPaise: number; status: string }[]>("/admin/settlements");
  const act = useAction();
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      {act.error && <Alert>{act.error}</Alert>}
      {msg && <Alert kind="success">{msg}</Alert>}
      <section className="card space-y-2">
        <h2 className="h2">Settlements</h2>
        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { const r = await api<{ created: number }>("/admin/settlements", { body: { action: "generate", periodStart: f.s, periodEnd: f.e } }); setMsg(`${r.created} settlement(s) created`); set.reload(); }); }}>
          <Field label="Period start"><input type="date" name="s" className="input" required /></Field><Field label="Period end (exclusive)"><input type="date" name="e" className="input" required /></Field><button className="btn-secondary">Generate</button>
        </form>
        <table className="w-full text-left text-sm"><tbody>{set.data?.map((s) => <tr key={s.id} className="border-b"><td className="py-1">{s.partner?.businessName ?? `Nurse ${s.nurseId?.slice(0, 8)}`}</td><td>{s.periodStart.slice(0, 10)} → {s.periodEnd.slice(0, 10)}</td><td>gross {rupees(s.grossInPaise)} · fee {rupees(s.commissionInPaise)} · net <b>{rupees(s.netInPaise)}</b></td><td><StatusBadge status={s.status} /></td><td>{s.status === "PENDING" && <button className="underline" onClick={() => { const ref = prompt("Payout reference (bank/UTR)"); if (ref) act.run(async () => { await api("/admin/settlements", { body: { action: "mark_paid", id: s.id, payoutRef: ref } }); set.reload(); }); }}>mark paid</button>}</td></tr>)}</tbody></table>
      </section>
      <section className="card space-y-2 overflow-x-auto">
        <h2 className="h2">Payments & reconciliation</h2>
        <table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-2">When</th><th>Booking</th><th>Order / payment</th><th>Amount</th><th>Status</th><th>Issues</th><th /></tr></thead><tbody>
          {rec.data?.map((p) => <tr key={p.id} className="border-b"><td className="py-1">{fmt(p.createdAt)}</td><td>{p.booking}</td><td className="text-xs">{p.providerOrderId}<br />{p.providerPaymentId}</td><td>{rupees(p.amountInPaise)}{p.refundedInPaise ? ` (−${rupees(p.refundedInPaise)})` : ""}</td><td><StatusBadge status={p.status} /></td><td className="text-xs text-alert-600">{p.issues.join(", ")}</td>
            <td>{p.status === "CAPTURED" && p.refundedInPaise < p.amountInPaise && <button className="underline" onClick={() => { const amt = prompt(`Refund amount in ₹ (max ${(p.amountInPaise - p.refundedInPaise) / 100})`); const reason = amt && prompt("Reason"); if (amt && reason) act.run(async () => { await api("/refunds", { body: { paymentId: p.id, amountInPaise: Math.round(Number(amt) * 100), reason } }); rec.reload(); }); }}>refund</button>}</td></tr>)}
        </tbody></table>
      </section>
    </div>
  );
}

export function Reports() {
  const [from, setFrom] = useState(new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10));
  const [to, setTo] = useState(new Date(Date.now() + 86_400_000).toISOString().slice(0, 10));
  return (
    <div className="card space-y-3">
      <p className="muted">CSV exports exclude clinical notes and street addresses. Each export is audited.</p>
      <div className="flex flex-wrap gap-2"><Field label="From"><input type="date" className="input" value={from} onChange={(e) => setFrom(e.target.value)} /></Field><Field label="To"><input type="date" className="input" value={to} onChange={(e) => setTo(e.target.value)} /></Field></div>
      <div className="flex flex-wrap gap-2">{["appointments", "stays", "payments", "nurses", "complaints"].map((k) => <a key={k} className="btn-secondary" href={`/api/v1/admin/reports?kind=${k}&from=${from}&to=${to}`}>{k}.csv</a>)}</div>
    </div>
  );
}

export function Templates() {
  const { data, reload } = useLoad<{ id: string; key: string; channel: string; language: string; subject: string | null; body: string }[]>("/admin/templates");
  const act = useAction();
  return (
    <div className="space-y-3">
      <Alert kind="info">SMS, email and WhatsApp templates must not contain clinical details (they may appear on lock screens). SMS templates must match DLT-registered text exactly; WhatsApp templates must be pre-approved by Meta.</Alert>
      {act.error && <Alert>{act.error}</Alert>}
      <form className="card grid gap-2 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api("/admin/templates", { method: "PUT", body: { key: f.key, channel: f.channel, language: f.language, subject: f.subject || undefined, body: f.body } }); reload(); }); }}>
        <Field label="Key"><input name="key" className="input" placeholder="appointment.confirmed" required /></Field>
        <Field label="Channel"><select name="channel" className="input"><option>SMS</option><option>IN_APP</option><option>EMAIL</option><option>WHATSAPP</option></select></Field>
        <Field label="Language"><input name="language" className="input" defaultValue="hi" required /></Field>
        <Field label="Email subject"><input name="subject" className="input" /></Field>
        <div className="sm:col-span-4"><Field label="Body ({{ref}}, {{when}}, {{status}}…)"><textarea name="body" className="input" rows={2} required /></Field></div>
        <button className="btn sm:col-span-4">Save template</button>
      </form>
      <div className="card overflow-x-auto"><table className="w-full text-left text-sm"><tbody>{data?.map((t) => <tr key={t.id} className="border-b"><td className="py-1">{t.key}</td><td>{t.channel}</td><td>{t.language}</td><td>{t.body}</td></tr>)}</tbody></table></div>
    </div>
  );
}

export function Cities() {
  const { data, reload } = useLoad<{ id: string; name: string; state: string; isActive: boolean }[]>("/admin/cities");
  const act = useAction();
  return (
    <div className="space-y-3">
      {act.error && <Alert>{act.error}</Alert>}
      <form className="card flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api("/admin/cities", { body: { name: f.name, state: f.state } }); reload(); }); }}>
        <Field label="City"><input name="name" className="input" required /></Field><Field label="State"><input name="state" className="input" required /></Field><button className="btn-secondary">Add city</button>
      </form>
      <div className="card"><ul className="text-sm">{data?.map((c) => <li key={c.id} className="flex justify-between py-1"><span>{c.name}, {c.state}</span><button className="underline" onClick={() => act.run(async () => { await api("/admin/cities", { body: { name: c.name, state: c.state, isActive: !c.isActive } }); reload(); })}>{c.isActive ? "active — deactivate" : "inactive — activate"}</button></li>)}</ul></div>
      <p className="muted">Service availability per city is set on each service (Service catalog). Travel limits are platform-wide (Travel & matching) and per nurse.</p>
    </div>
  );
}

export function Suspicious() {
  const { data } = useLoad<{ kind: string; subject: string; count: number }[]>("/admin/suspicious");
  return <div className="card space-y-2"><p className="muted">Rule-based signals from the last 7 days. These never suspend anyone automatically.</p>{data?.length === 0 && <p>No signals.</p>}<ul className="text-sm">{data?.map((s, i) => <li key={i}>{s.kind.replaceAll("_", " ")} · {s.subject} · {s.count}</li>)}</ul></div>;
}
