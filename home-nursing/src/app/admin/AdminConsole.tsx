"use client";
import { useCallback, useEffect, useState } from "react";
import { api, fmt, rupees } from "@/lib/client";
import { Alert, Field, StatusBadge, useAction } from "@/components/ui";
import { Authorizations, Bookings, Cities, Hospitals, Partners, Payments, Reports, Reviews, Suspicious, Templates, Users } from "./AdminMore";

const TABS = [
  ["overview", "Overview", "admin.access"], ["nurses", "Nurse verification", "nurse.verify"], ["auth", "Prescriptions", "authorization.review"], ["bookings", "Bookings", "appointment.view_ops"], ["users", "Users", "users.manage"],
  ["hospitals", "Hospitals", "hospital.manage"], ["partners", "Partners", "partners.manage"], ["reviews", "Reviews", "reviews.moderate"], ["payments", "Payments & settlements", "payments.manage"], ["reports", "Reports", "reports.export"],
  ["templates", "Notification templates", "templates.manage"], ["cities", "Cities", "admin.access"], ["signals", "Suspicious activity", "complaint.manage"], ["travel", "Travel & matching", "admin.access"], ["services", "Service catalog", "catalog.manage"],
  ["properties", "Property verification", "property.verify"], ["complaints", "Complaints & incidents", "complaint.manage"], ["compliance", "Regulatory readiness", "compliance.manage"],
  ["privacy", "Privacy requests", "privacy.manage"], ["flags", "Feature flags", "admin.access"], ["audit", "Audit log", "audit.read"],
] as const;

export function AdminConsole({ permissions }: { permissions: string[] }) {
  const tabs = TABS.filter((t) => permissions.includes(t[2]));
  const [tab, setTab] = useState<string>(tabs[0]?.[0] ?? "overview");
  return (
    <div className="space-y-6">
      <h1 className="h1">Admin</h1>
      <nav className="flex flex-wrap gap-2" aria-label="Admin sections">{tabs.map(([k, l]) => <button key={k} onClick={() => setTab(k)} className={tab === k ? "btn" : "btn-secondary"}>{l}</button>)}</nav>
      {tab === "overview" && <Overview />}
      {tab === "nurses" && <Nurses />}
      {tab === "travel" && <Travel canWrite={permissions.includes("settings.write")} />}
      {tab === "services" && <Services />}
      {tab === "properties" && <Properties />}
      {tab === "complaints" && <Complaints />}
      {tab === "compliance" && <Compliance />}
      {tab === "privacy" && <Privacy />}
      {tab === "flags" && <Flags canWrite={permissions.includes("flags.write")} />}
      {tab === "audit" && <Audit />}
      {tab === "auth" && <Authorizations />}
      {tab === "bookings" && <Bookings />}
      {tab === "users" && <Users isAdmin={permissions.includes("flags.write")} />}
      {tab === "hospitals" && <Hospitals />}
      {tab === "partners" && <Partners />}
      {tab === "reviews" && <Reviews />}
      {tab === "payments" && <Payments />}
      {tab === "reports" && <Reports />}
      {tab === "templates" && <Templates />}
      {tab === "cities" && <Cities />}
      {tab === "signals" && <Suspicious />}
    </div>
  );
}

function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const reload = useCallback(() => { api<T>(path).then(setData).catch((e) => setErr(e.message)); }, [path]);
  useEffect(reload, [reload]);
  return { data, err, reload };
}

function Overview() {
  const { data } = useLoad<Record<string, unknown> & { appointmentsByStatus: Record<string, number>; capturedInPaise: number }>("/admin/metrics");
  if (!data) return <p className="muted">Loading…</p>;
  const tiles = [["Nurses pending verification", data.nursesPending], ["Approved nurses", data.nursesApproved], ["Open complaints", data.openComplaints], ["Stay requests pending", data.staysRequested], ["Open privacy requests", data.privacyOpen], ["Payments captured", rupees(data.capturedInPaise)]];
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">{tiles.map(([l, v]) => <div key={l as string} className="card"><p className="muted">{l as string}</p><p className="text-2xl font-bold">{String(v)}</p></div>)}</div>
      <div className="card"><h2 className="h2 mb-2">Appointments by status</h2><div className="flex flex-wrap gap-3 text-sm">{Object.entries(data.appointmentsByStatus).map(([k, v]) => <span key={k}><StatusBadge status={k} /> {v}</span>)}</div></div>
    </div>
  );
}

type QNurse = { id: string; displayName: string; status: string; user: { phone: string }; registrations: { id: string; councilName: string; registrationNumber: string; state: string; status: string }[]; qualifications: { id: string; code: string; verificationStatus: string }[]; documents: { id: string; kind: string; status: string; mandatory: boolean }[]; eligibilities: { serviceId: string; status: string; service: { name: string } }[] };
function Nurses() {
  const [status, setStatus] = useState("PENDING_VERIFICATION");
  const { data, reload } = useLoad<QNurse[]>(`/admin/nurses?status=${status}`);
  const act = useAction();
  const decide = (path: string, body: unknown) => act.run(async () => { await api(path, { body }); reload(); });
  return (
    <div className="space-y-3">
      <select className="input w-fit" value={status} onChange={(e) => setStatus(e.target.value)}>{["PENDING_VERIFICATION", "APPROVED", "REJECTED", "SUSPENDED", "DRAFT"].map((s) => <option key={s}>{s}</option>)}</select>
      {act.error && <Alert>{act.error}</Alert>}
      {data?.length === 0 && <p className="muted">Queue is empty.</p>}
      {data?.map((n) => (
        <div key={n.id} className="card space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{n.displayName} <span className="muted">{n.user.phone}</span></p><StatusBadge status={n.status} /></div>
          <div className="grid gap-3 md:grid-cols-3 text-sm">
            <div><p className="font-medium">Registrations</p>{n.registrations.map((r) => <div key={r.id} className="mt-1">{r.councilName} · {r.registrationNumber} <StatusBadge status={r.status} />{r.status === "PENDING" && <span className="ml-1 space-x-1"><button className="underline" onClick={() => decide(`/admin/credentials/registrations/${r.id}`, { decision: "VERIFIED", method: "COUNCIL_PORTAL_CHECK" })}>verify</button><button className="underline" onClick={() => decide(`/admin/credentials/registrations/${r.id}`, { decision: "REJECTED", method: "COUNCIL_PORTAL_CHECK" })}>reject</button></span>}</div>)}</div>
            <div><p className="font-medium">Documents</p>{n.documents.map((d) => <div key={d.id} className="mt-1">{d.kind} <StatusBadge status={d.status} /> <button className="underline" onClick={() => act.run(async () => { const u = await api<{ url: string }>(`/admin/credentials/documents/${d.id}`); window.open(u.url, "_blank", "noopener"); })}>open</button>{d.status === "PENDING" && <span className="ml-1 space-x-1"><button className="underline" onClick={() => decide(`/admin/credentials/documents/${d.id}`, { decision: "VERIFIED", method: "MANUAL_DOCUMENT_REVIEW" })}>verify</button><button className="underline" onClick={() => decide(`/admin/credentials/documents/${d.id}`, { decision: "REJECTED", method: "MANUAL_DOCUMENT_REVIEW" })}>reject</button></span>}</div>)}</div>
            <div><p className="font-medium">Qualifications & services</p>{n.qualifications.map((q) => <div key={q.id} className="mt-1">{q.code} <StatusBadge status={q.verificationStatus} />{q.verificationStatus === "PENDING" && <button className="ml-1 underline" onClick={() => decide(`/admin/qualifications/${q.id}`, { decision: "VERIFIED" })}>verify</button>}</div>)}{n.eligibilities.map((e) => <div key={e.serviceId} className="mt-1">{e.service.name} <StatusBadge status={e.status} />{e.status === "PENDING" && <button className="ml-1 underline" onClick={() => decide(`/admin/nurses/${n.id}/eligibility`, { serviceId: e.serviceId })}>approve</button>}</div>)}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            {n.status !== "APPROVED" && <button className="btn" onClick={() => decide(`/admin/nurses/${n.id}/status`, { status: "APPROVED" })}>Approve nurse</button>}
            {n.status === "PENDING_VERIFICATION" && <button className="btn-secondary" onClick={() => { const reason = prompt("Reason for rejection"); if (reason) decide(`/admin/nurses/${n.id}/status`, { status: "REJECTED", reason }); }}>Reject</button>}
            {n.status === "APPROVED" && <button className="btn-danger" onClick={() => { const reason = prompt("Reason for suspension"); if (reason) decide(`/admin/nurses/${n.id}/status`, { status: "SUSPENDED", reason }); }}>Suspend</button>}
            {n.status === "SUSPENDED" && <button className="btn-secondary" onClick={() => decide(`/admin/nurses/${n.id}/status`, { status: "APPROVED", reason: "reinstated" })}>Reinstate</button>}
          </div>
        </div>
      ))}
    </div>
  );
}

type Matching = { maxTravelMinutes: number; maxRoadDistanceKm: number | null; fallbackRadiusKm: number; allowPatientExpansion: boolean; expansionMaxMinutes: number; travelBufferMinutes: number; appointmentBufferMinutes: number; routingUnavailablePolicy: string; routeCacheSeconds: number; bookingCutoffMinutes: number; maxResults: number; weights: Record<string, number> };
function Travel({ canWrite }: { canWrite: boolean }) {
  const { data, reload } = useLoad<{ matching: Matching; commerce: Record<string, number> }>("/admin/settings");
  const act = useAction();
  const [saved, setSaved] = useState(false);
  if (!data) return <p className="muted">Loading…</p>;
  const m = data.matching;
  const nums: [keyof Matching, string][] = [["maxTravelMinutes", "Maximum road travel time (minutes)"], ["fallbackRadiusKm", "Coarse pre-filter radius (km) — not used as travel time"], ["expansionMaxMinutes", "Expanded limit when permitted (minutes)"], ["travelBufferMinutes", "Travel buffer before visit (minutes)"], ["appointmentBufferMinutes", "Buffer after visit (minutes)"], ["routeCacheSeconds", "Route cache duration (seconds)"], ["bookingCutoffMinutes", "Booking cutoff (minutes before start)"], ["maxResults", "Maximum results"]];
  return (
    <form className="card max-w-2xl space-y-3" onSubmit={(e) => {
      e.preventDefault();
      const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
      const patch: Record<string, unknown> = Object.fromEntries(nums.map(([k]) => [k, Number(f[k])]));
      patch.maxRoadDistanceKm = f.maxRoadDistanceKm ? Number(f.maxRoadDistanceKm) : null;
      patch.allowPatientExpansion = f.allowPatientExpansion === "on";
      patch.routingUnavailablePolicy = f.routingUnavailablePolicy;
      patch.weights = Object.fromEntries(Object.keys(m.weights).map((k) => [k, Number(f[`w_${k}`])]));
      act.run(async () => { await api("/admin/settings", { method: "PUT", body: { key: "matching", patch } }); setSaved(true); reload(); });
    }}>
      <p className="muted">Changes take effect immediately without redeploying and are recorded in the audit log.</p>
      {nums.map(([k, l]) => <Field key={k} label={l}><input name={k} type="number" className="input" defaultValue={m[k] as number} disabled={!canWrite} /></Field>)}
      <Field label="Optional max road distance (km)"><input name="maxRoadDistanceKm" type="number" className="input" defaultValue={m.maxRoadDistanceKm ?? ""} disabled={!canWrite} /></Field>
      <Field label="When a travel estimate is unavailable"><select name="routingUnavailablePolicy" className="input" defaultValue={m.routingUnavailablePolicy} disabled={!canWrite}><option value="EXCLUDE">Exclude the nurse (safe default)</option><option value="INCLUDE_FLAGGED_MANUAL_CONFIRM">Include, flagged for manual confirmation</option></select></Field>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="allowPatientExpansion" defaultChecked={m.allowPatientExpansion} disabled={!canWrite} /> Allow patients to request an expanded search</label>
      <fieldset className="grid grid-cols-2 gap-3 sm:grid-cols-5"><legend className="label">Ranking weights</legend>{Object.entries(m.weights).map(([k, v]) => <Field key={k} label={k}><input name={`w_${k}`} type="number" step="0.05" className="input" defaultValue={v} disabled={!canWrite} /></Field>)}</fieldset>
      {act.error && <Alert>{act.error}</Alert>}
      {saved && <Alert kind="success">Saved.</Alert>}
      {canWrite && <button className="btn" disabled={act.busy}>Save settings</button>}
    </form>
  );
}

type Svc = { id: string; name: string; isActive: boolean; isInvasive: boolean; clinicalReviewApproved: boolean; basePriceInPaise: number; durationMinutes: number; requiresPrescription: boolean };
function Services() {
  const { data, reload } = useLoad<Svc[]>("/admin/services");
  const act = useAction();
  const patch = (body: unknown) => act.run(async () => { await api("/admin/services", { method: "PATCH", body }); reload(); });
  return (
    <div className="card overflow-x-auto">
      {act.error && <Alert>{act.error}</Alert>}
      <table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-2">Service</th><th>Price</th><th>Duration</th><th>Status</th><th>Clinical review</th></tr></thead><tbody>
        {data?.map((s) => (
          <tr key={s.id} className="border-b align-top">
            <td className="py-2">{s.name}{s.requiresPrescription && <span className="ml-1 badge bg-amber-100 text-amber-900">Rx</span>}</td>
            <td><input className="input w-24" type="number" defaultValue={s.basePriceInPaise / 100} onBlur={(e) => Number(e.target.value) * 100 !== s.basePriceInPaise && patch({ id: s.id, basePriceInPaise: Math.round(Number(e.target.value) * 100) })} /></td>
            <td>{s.durationMinutes} min</td>
            <td><button className="underline" onClick={() => patch({ id: s.id, isActive: !s.isActive })}>{s.isActive ? "Active" : "Inactive"}</button></td>
            <td>{s.isInvasive ? (s.clinicalReviewApproved ? <span>Approved <button className="underline" onClick={() => patch({ id: s.id, clinicalReviewApproved: false })}>revoke</button></span> : <button className="underline" onClick={() => { const who = prompt("Name and registration of the reviewing clinician"); if (who) patch({ id: s.id, clinicalReviewApproved: true, clinicalReviewer: who }); }}>Record sign-off</button>) : "Not required"}</td>
          </tr>
        ))}
      </tbody></table>
    </div>
  );
}

function Properties() {
  const { data, reload } = useLoad<{ id: string; name: string; city: string; partner: { businessName: string } }[]>("/admin/properties?status=PENDING");
  const act = useAction();
  return <div className="space-y-2">{act.error && <Alert>{act.error}</Alert>}{data?.length === 0 && <p className="muted">No properties awaiting verification.</p>}{data?.map((p) => <div key={p.id} className="card flex flex-wrap items-center justify-between gap-2"><span><b>{p.name}</b> · {p.city} · {p.partner.businessName}</span><span className="flex gap-2"><button className="btn" onClick={() => act.run(async () => { await api("/admin/properties", { body: { id: p.id, decision: "VERIFIED" } }); reload(); })}>Verify</button><button className="btn-secondary" onClick={() => act.run(async () => { await api("/admin/properties", { body: { id: p.id, decision: "REJECTED" } }); reload(); })}>Reject</button></span></div>)}</div>;
}

function Complaints() {
  const { data, reload } = useLoad<{ complaints: { id: string; category: string; severity: string; description: string; status: string; createdAt: string }[]; incidents: { id: string; kind: string; description: string; createdAt: string }[] }>("/admin/complaints");
  const act = useAction();
  const upd = (id: string, status: string) => { const resolution = status === "INVESTIGATING" ? undefined : prompt("Resolution notes") ?? undefined; act.run(async () => { await api("/admin/complaints", { method: "PATCH", body: { id, status, resolution } }); reload(); }); };
  return (
    <div className="space-y-4">
      {act.error && <Alert>{act.error}</Alert>}
      <h2 className="h2">Complaints</h2>
      {data?.complaints.length === 0 && <p className="muted">No open complaints.</p>}
      {data?.complaints.map((c) => <div key={c.id} className="card space-y-2"><div className="flex flex-wrap justify-between gap-2"><span><StatusBadge status={c.severity} /> {c.category} · {fmt(c.createdAt)}</span><StatusBadge status={c.status} /></div><p className="text-sm">{c.description}</p><div className="flex gap-2">{c.status === "OPEN" && <button className="btn-secondary" onClick={() => upd(c.id, "INVESTIGATING")}>Investigate</button>}<button className="btn-secondary" onClick={() => upd(c.id, "RESOLVED")}>Resolve</button><button className="btn-secondary" onClick={() => upd(c.id, "DISMISSED")}>Dismiss</button></div></div>)}
      <h2 className="h2">Incidents</h2>
      {data?.incidents.map((i) => <div key={i.id} className="card text-sm"><b>{i.kind}</b> · {fmt(i.createdAt)}<p>{i.description}</p></div>)}
    </div>
  );
}

type CItem = { id: string; jurisdiction: string; category: string; responsibleParty: string; requirement: string; applicability: string; status: string; issuingAuthority: string | null; renewalDate: string | null; blocksOperation: string | null; exceptionNote: string | null };
function Compliance() {
  const { data, reload } = useLoad<CItem[]>("/compliance");
  const act = useAction();
  const upd = (body: Record<string, unknown>) => act.run(async () => { await api("/compliance", { method: "PATCH", body }); reload(); });
  return (
    <div className="space-y-3">
      <Alert kind="warn">This registry records the review status of potential obligations. It does not establish that the platform is compliant. Applicability must be confirmed by qualified Indian legal counsel.</Alert>
      {act.error && <Alert>{act.error}</Alert>}
      <form className="card grid gap-3 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>; act.run(async () => { await api("/compliance", { body: { jurisdiction: f.jurisdiction, category: f.category, responsibleParty: f.party, requirement: f.requirement, applicability: "PENDING_LEGAL_REVIEW", blocksOperation: f.blocks || null } }); (e.target as HTMLFormElement).reset(); reload(); }); }}>
        <Field label="Jurisdiction" hint="IN for national, or state name"><input name="jurisdiction" className="input" required /></Field>
        <Field label="Category"><input name="category" className="input" required /></Field>
        <Field label="Responsible party"><select name="party" className="input">{["PLATFORM", "NURSE", "CLINICAL_ESTABLISHMENT", "LAB_PARTNER", "ACCOMMODATION", "PAYMENT_TECH"].map((p) => <option key={p}>{p}</option>)}</select></Field>
        <div className="sm:col-span-2"><Field label="Requirement"><input name="requirement" className="input" required /></Field></div>
        <Field label="Blocks operation until cleared"><select name="blocks" className="input"><option value="">No</option><option value="NURSING_BOOKINGS">Nursing bookings</option><option value="ACCOMMODATION_BOOKINGS">Accommodation bookings</option></select></Field>
        <button className="btn sm:col-span-3" disabled={act.busy}>Add item</button>
      </form>
      <div className="card overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-2">Jurisdiction</th><th>Party</th><th>Requirement</th><th>Applicability</th><th>Status</th><th>Gate</th></tr></thead><tbody>
        {data?.map((c) => (
          <tr key={c.id} className="border-b align-top">
            <td className="py-2">{c.jurisdiction}</td><td>{c.responsibleParty}</td><td className="max-w-md">{c.requirement}<br /><span className="text-xs text-ink-500">{c.issuingAuthority}</span></td>
            <td><select className="input" value={c.applicability} onChange={(e) => upd({ id: c.id, applicability: e.target.value })}>{["PENDING_LEGAL_REVIEW", "POTENTIALLY_APPLICABLE", "CONFIRMED", "NOT_APPLICABLE_AFTER_REVIEW"].map((x) => <option key={x}>{x}</option>)}</select></td>
            <td><select className="input" value={c.status} onChange={(e) => { const s = e.target.value; if (s === "EXCEPTION_RECORDED") { const note = prompt("Document the legal basis for this exception"); if (note) upd({ id: c.id, status: s, exceptionNote: note }); } else upd({ id: c.id, status: s }); }}>{["OPEN", "IN_PROGRESS", "SATISFIED", "EXCEPTION_RECORDED", "LAPSED"].map((x) => <option key={x}>{x}</option>)}</select></td>
            <td>{c.blocksOperation ?? "—"}</td>
          </tr>
        ))}
      </tbody></table></div>
    </div>
  );
}

function Privacy() {
  const { data, reload } = useLoad<{ id: string; kind: string; status: string; dueBy: string; details: string | null }[]>("/admin/privacy");
  const act = useAction();
  const setStatus = (id: string, status: string) => { const note = prompt("Note (what was done)") ?? undefined; act.run(async () => { await api("/admin/privacy", { body: { id, action: "set_status", status, note } }); reload(); }); };
  return <div className="space-y-2">{act.error && <Alert>{act.error}</Alert>}{data?.length === 0 && <p className="muted">No open requests.</p>}{data?.map((r) => <div key={r.id} className="card flex flex-wrap items-center justify-between gap-2"><span><b>{r.kind}</b> · <StatusBadge status={r.status} /> · due {fmt(r.dueBy)}<br /><span className="muted">{r.details}</span></span><span className="flex gap-2">{r.status === "RECEIVED" && <button className="btn-secondary" onClick={() => setStatus(r.id, "IN_PROGRESS")}>Start</button>}{r.kind !== "DELETION" && <button className="btn-secondary" onClick={() => setStatus(r.id, "COMPLETED")}>Complete</button>}<button className="btn-secondary" onClick={() => setStatus(r.id, "REJECTED")}>Reject</button></span>{r.kind === "DELETION" && <button className="btn-danger" onClick={() => confirm("Execute deletion? Identity fields will be pseudonymised; records under legal retention are kept.") && act.run(async () => { await api("/admin/privacy", { body: { id: r.id, action: "execute_deletion" } }); reload(); })}>Execute deletion</button>}</div>)}</div>;
}

function Flags({ canWrite }: { canWrite: boolean }) {
  const { data, reload } = useLoad<{ key: string; enabled: boolean; description: string }[]>("/admin/flags");
  const act = useAction();
  return <div className="space-y-2">{act.error && <Alert>{act.error}</Alert>}{data?.map((f) => <div key={f.key} className="card flex items-center justify-between gap-3"><span><b>{f.key}</b><br /><span className="muted">{f.description}</span></span><button className={f.enabled ? "btn" : "btn-secondary"} disabled={!canWrite || act.busy} onClick={() => act.run(async () => { await api("/admin/flags", { method: "PUT", body: { key: f.key, enabled: !f.enabled } }); reload(); })}>{f.enabled ? "On" : "Off"}</button></div>)}</div>;
}

function Audit() {
  const { data } = useLoad<{ id: string; action: string; entityType: string; entityId: string | null; actorUserId: string | null; createdAt: string }[]>("/admin/audit?limit=100");
  return <div className="card overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-2">When</th><th>Action</th><th>Entity</th><th>Actor</th></tr></thead><tbody>{data?.map((a) => <tr key={a.id} className="border-b"><td className="py-1">{fmt(a.createdAt)}</td><td>{a.action}</td><td>{a.entityType} {a.entityId?.slice(0, 8)}</td><td>{a.actorUserId?.slice(0, 8)}</td></tr>)}</tbody></table></div>;
}
