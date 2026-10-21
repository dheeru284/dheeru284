import Link from "next/link";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function Services() {
  const services = await prisma.nursingService.findMany({ where: { isActive: true }, include: { category: true }, orderBy: [{ categoryId: "asc" }, { name: "asc" }] });
  return (
    <div className="space-y-6">
      <h1 className="h1">Nursing services</h1>
      <p className="muted max-w-2xl">Prices are starting prices; nurses may set their own. Services marked “pending clinical review” are not yet bookable.</p>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {services.map((s) => {
          const bookable = !s.isInvasive || s.clinicalReviewApproved;
          return (
            <li key={s.id} className="card flex flex-col">
              <span className="text-xs font-medium uppercase tracking-wide text-brand-600">{s.category.name}</span>
              <h2 className="mt-1 font-semibold">{s.name}</h2>
              <p className="muted mt-1 flex-1">{s.description}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="badge bg-slate-100">{s.durationMinutes} min</span>
                <span className="badge bg-slate-100">from ₹{(s.basePriceInPaise / 100).toLocaleString("en-IN")}</span>
                {s.requiresPrescription && <span className="badge bg-amber-100 text-amber-900">Prescription required</span>}
                {!bookable && <span className="badge bg-slate-200 text-ink-700">Pending clinical review</span>}
              </div>
              {bookable && <Link href={`/patient/book?service=${s.id}`} className="btn-secondary mt-4">Book</Link>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
