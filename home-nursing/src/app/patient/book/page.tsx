import { prisma } from "@/lib/db";
import { requirePage } from "@/lib/page-auth";
import { BookingFlow } from "./BookingFlow";

export const dynamic = "force-dynamic";

export default async function BookPage({ searchParams }: { searchParams: Promise<{ service?: string }> }) {
  const p = await requirePage("appointment.book", "/patient/book");
  const [services, patients, addresses] = await Promise.all([
    prisma.nursingService.findMany({ where: { isActive: true }, orderBy: { name: "asc" } }),
    prisma.patientProfile.findMany({ where: { deletedAt: null, OR: [{ accountUserId: p.userId }, { caregivers: { some: { caregiverUserId: p.userId, canBook: true } } }] }, select: { id: true, fullName: true } }),
    prisma.patientAddress.findMany({ where: { userId: p.userId, deletedAt: null }, select: { id: true, label: true, line1: true, city: true } }),
  ]);
  const bookable = services.filter((s) => !s.isInvasive || s.clinicalReviewApproved).map((s) => ({ id: s.id, name: s.name, durationMinutes: s.durationMinutes, requiresPrescription: s.requiresPrescription }));
  return (
    <div className="space-y-6">
      <h1 className="h1">Book a nurse</h1>
      <BookingFlow services={bookable} patients={patients} addresses={addresses} initialService={(await searchParams).service} />
    </div>
  );
}
