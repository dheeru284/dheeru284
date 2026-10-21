import Link from "next/link";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function Hospitals({ searchParams }: { searchParams: Promise<{ q?: string; city?: string }> }) {
  const { q, city } = await searchParams;
  const list = await prisma.hospital.findMany({
    where: { isActive: true, mergedIntoId: null, ...(city ? { city } : {}), ...(q ? { OR: [{ name: { contains: q, mode: "insensitive" } }, { address: { contains: q, mode: "insensitive" } }] } : {}) },
    orderBy: [{ city: "asc" }, { name: "asc" }],
    take: 100,
  });
  const cities = await prisma.hospital.findMany({ where: { isActive: true }, distinct: ["city"], select: { city: true } });
  return (
    <div className="space-y-4">
      <h1 className="h1">Hospital directory</h1>
      <p className="muted max-w-2xl">A reference directory to help you find stays nearby. Listing does not imply a partnership; partnerships are shown only where an agreement exists.</p>
      <form className="flex flex-wrap gap-2"><input name="q" defaultValue={q} className="input max-w-xs" placeholder="Search name or area" /><select name="city" defaultValue={city ?? ""} className="input w-44"><option value="">All cities</option>{cities.map((c) => <option key={c.city}>{c.city}</option>)}</select><button className="btn">Search</button></form>
      <ul className="grid gap-3 sm:grid-cols-2">
        {list.map((h) => (
          <li key={h.id} className="card space-y-1">
            <p className="font-semibold">{h.name}</p>
            <p className="muted">{h.address}, {h.city}, {h.state} {h.pincode}</p>
            <p className="text-xs">{h.verificationStatus === "VERIFIED" ? `Details verified ${h.lastVerifiedAt?.toISOString().slice(0, 10) ?? ""}` : "Details not yet verified"} · Source: {h.dataSource}{h.hasFormalPartnership && <span className="ml-1 badge bg-emerald-100 text-emerald-800">Partner hospital</span>}</p>
            <Link className="text-sm text-brand-700 underline" href={`/stays?hospital=${h.id}`}>Find stays nearby</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
