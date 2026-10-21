import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { DemoBadge } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function NursePublic({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const n = await prisma.nurseProfile.findFirst({
    where: { id, status: "APPROVED" },
    include: { qualifications: { where: { verificationStatus: "VERIFIED" } }, registrations: { where: { status: "VERIFIED" } }, serviceAreas: true, eligibilities: { where: { status: "APPROVED" }, include: { service: true } }, reviews: { where: { moderationStatus: "VISIBLE" }, orderBy: { createdAt: "desc" }, take: 20 } },
  });
  if (!n) notFound();
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="card space-y-2">
        <h1 className="h1">{n.displayName} {n.isDemo && <DemoBadge />}</h1>
        <p className="text-sm"><span className="badge bg-emerald-100 text-emerald-800">Registration verified</span> {n.registrations.map((r) => `${r.councilName}`).join(", ")}</p>
        <p className="muted">{n.qualifications.map((q) => q.code).join(", ")} · {n.yearsExperience} yrs · {n.gender.toLowerCase()} · speaks {n.languages.join(", ")} · {n.serviceAreas[0]?.label}</p>
        {n.bio && <p>{n.bio}</p>}
        <p className="text-sm">{n.ratingCount ? `★ ${n.ratingAvg.toFixed(1)} from ${n.ratingCount} reviews` : "No reviews yet"} · {n.completedVisits} completed visits</p>
      </div>
      <div className="card"><h2 className="h2 mb-2">Approved services</h2><ul className="text-sm">{n.eligibilities.filter((e) => e.service.isActive && (!e.service.isInvasive || e.service.clinicalReviewApproved)).map((e) => <li key={e.id} className="flex justify-between py-1"><span>{e.service.name}</span><Link className="text-brand-700 underline" href={`/patient/book?service=${e.service.id}`}>Book</Link></li>)}</ul></div>
      <div className="card space-y-2"><h2 className="h2">Reviews</h2>{n.reviews.length ? n.reviews.map((r) => <p key={r.id} className="text-sm">{"★".repeat(r.rating)} {r.comment}</p>) : <p className="muted">No reviews yet.</p>}</div>
    </div>
  );
}
