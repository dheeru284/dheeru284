import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { DemoBadge } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function Property({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const p = await prisma.accommodationProperty.findFirst({ where: { id, isActive: true, verificationStatus: "VERIFIED" }, include: { images: true, amenities: true, rates: { orderBy: { validFrom: "desc" }, take: 1 }, units: { select: { id: true } } } });
  if (!p) notFound();
  const r = p.rates[0];
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="h1">{p.name} {p.isDemo && <DemoBadge />}</h1>
      {p.images.length > 0 && <div className="grid grid-cols-2 gap-2">{p.images.map((i) => (
        // eslint-disable-next-line @next/next/no-img-element -- signed redirect URLs are not compatible with next/image optimisation
        <img key={i.id} src={`/api/v1/media/property-images/${i.id}`} alt={i.alt} className="h-48 w-full rounded-xl object-cover" />))}</div>}
      <div className="card space-y-2">
        <p className="muted">{p.propertyType.replaceAll("_", " ").toLowerCase()} · {p.city} · {p.bedrooms} bed · {p.bathrooms} bath · up to {p.maxGuests} guests · {p.units.length} unit(s) · min {p.minStayNights} nights</p>
        <p>{p.description}</p>
        {r && <p className="text-sm">₹{(r.nightlyInPaise / 100).toLocaleString("en-IN")}/night{r.monthlyInPaise ? ` · ₹${(r.monthlyInPaise / 100).toLocaleString("en-IN")} per 30 nights` : ""}{r.extendedStayDiscountPct ? ` · ${r.extendedStayDiscountPct}% off 14+ nights` : ""}{r.depositInPaise ? ` · ₹${(r.depositInPaise / 100).toLocaleString("en-IN")} refundable deposit` : ""}</p>}
        <p className="text-sm">Amenities: {p.amenities.map((a) => a.amenity.replaceAll("_", " ")).join(", ")}</p>
        <p className="text-sm">Accessibility: {p.accessibility.map((a) => a.replaceAll("_", " ")).join(", ") || "not specified"}</p>
        {p.houseRules && <p className="text-sm">House rules: {p.houseRules}</p>}
        <p className="text-sm">Cancellation: {p.cancellationPolicy}</p>
        <p className="text-xs text-ink-500">Listing verified by our team. Questions about the property go through support; we do not share your medical information with properties.</p>
      </div>
    </div>
  );
}
