import Link from "next/link";
import { prisma } from "@/lib/db";
import { requirePage } from "@/lib/page-auth";
import { formatInTz } from "@/lib/time";
import { Empty, StatusBadge } from "@/components/ui";
import { PauseToggle } from "./PauseToggle";

export const dynamic = "force-dynamic";

export default async function NurseHome() {
  const p = await requirePage("nurse.self", "/nurse");
  const n = await prisma.nurseProfile.findUnique({ where: { userId: p.userId }, include: { documents: true, reviews: { where: { moderationStatus: "VISIBLE" }, orderBy: { createdAt: "desc" }, take: 5 } } });
  if (!n) return <Empty title="Set up your nurse profile to get started"><Link className="btn mt-3" href="/nurse/profile">Set up profile</Link></Empty>;
  const appts = await prisma.appointment.findMany({ where: { nurseId: n.id }, include: { service: true, address: { select: { city: true, locality: true } } }, orderBy: { startAt: "asc" } });
  const completed = appts.filter((a) => a.status === "COMPLETED");
  const earnings = completed.reduce((s, a) => s + a.amountInPaise - a.commissionInPaise, 0);
  const expiring = n.documents.filter((d) => d.expiresOn && d.expiresOn.getTime() < Date.now() + 30 * 86_400_000);
  const groups = { "Requests awaiting your response": appts.filter((a) => a.status === "AWAITING_NURSE_ACCEPTANCE"), Upcoming: appts.filter((a) => ["CONFIRMED", "NURSE_EN_ROUTE", "NURSE_ARRIVED", "IN_PROGRESS"].includes(a.status)), Past: appts.filter((a) => ["COMPLETED", "CANCELLED", "NO_SHOW", "RESCHEDULED"].includes(a.status)).reverse().slice(0, 10) };
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="h1">Hello, {n.displayName}</h1>
        <div className="flex gap-2"><Link href="/nurse/profile" className="btn-secondary">Profile & availability</Link></div>
      </div>
      <div className="grid gap-4 sm:grid-cols-4">
        <div className="card"><p className="muted">Verification</p><StatusBadge status={n.status} /></div>
        <div className="card"><p className="muted">Completed visits</p><p className="text-2xl font-bold">{completed.length}</p></div>
        <div className="card"><p className="muted">Earnings after commission</p><p className="text-2xl font-bold">₹{(earnings / 100).toLocaleString("en-IN")}</p><p className="text-xs text-ink-500">Settlement status shown once payouts are configured.</p></div>
        <div className="card"><p className="muted">Availability</p><PauseToggle paused={n.isPaused} /></div>
      </div>
      {n.status !== "APPROVED" && <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">You are not bookable until your credentials are verified and your profile is approved. <Link className="underline" href="/nurse/profile">Complete your profile</Link>.</div>}
      {expiring.length > 0 && <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{expiring.length} credential(s) expire within 30 days. Upload renewed copies to stay bookable.</div>}
      {Object.entries(groups).map(([title, list]) => (
        <section key={title} className="space-y-2">
          <h2 className="h2">{title}</h2>
          {list.length ? list.map((a) => (
            <Link key={a.id} href={`/nurse/appointments/${a.id}`} className="card flex flex-wrap items-center justify-between gap-2 hover:border-brand-500">
              <span><b>{a.service.name}</b> · {a.address.locality ? `${a.address.locality}, ` : ""}{a.address.city}<br /><span className="muted">{formatInTz(a.startAt)} · ~{a.estTravelMinutes ?? "?"} min travel · ₹{(a.amountInPaise / 100).toLocaleString("en-IN")}</span></span>
              <StatusBadge status={a.status} />
            </Link>
          )) : <p className="muted">Nothing here.</p>}
        </section>
      ))}
      <section className="space-y-2"><h2 className="h2">Recent reviews</h2>{n.reviews.length ? n.reviews.map((r) => <div key={r.id} className="card">{"★".repeat(r.rating)} <span className="muted">{r.comment}</span></div>) : <p className="muted">No reviews yet.</p>}</section>
      <Link href="/account" className="text-sm text-brand-700 underline">Report an unsafe situation or contact support</Link>
    </div>
  );
}
