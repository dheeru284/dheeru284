import Link from "next/link";
import { prisma } from "@/lib/db";
import { requirePage } from "@/lib/page-auth";
import { formatInTz } from "@/lib/time";
import { StatusBadge, Empty } from "@/components/ui";
import { AddPatientForm, AddAddressForm } from "./forms";

export const dynamic = "force-dynamic";

export default async function PatientDashboard() {
  const p = await requirePage("patient.self", "/patient");
  const [profiles, addresses, appts, stays] = await Promise.all([
    prisma.patientProfile.findMany({ where: { deletedAt: null, OR: [{ accountUserId: p.userId }, { caregivers: { some: { caregiverUserId: p.userId } } }] } }),
    prisma.patientAddress.findMany({ where: { userId: p.userId, deletedAt: null } }),
    prisma.appointment.findMany({ where: { bookedByUserId: p.userId }, include: { service: true, nurse: true, patient: true }, orderBy: { startAt: "desc" }, take: 20 }),
    prisma.accommodationBooking.findMany({ where: { userId: p.userId }, include: { unit: { include: { property: true } } }, orderBy: { checkIn: "desc" }, take: 10 }),
  ]);
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="h1">My care</h1><Link href="/patient/book" className="btn">Book a nurse</Link></div>
      <section className="grid gap-6 md:grid-cols-2">
        <div className="card space-y-3">
          <h2 className="h2">People I care for</h2>
          {profiles.length ? <ul className="divide-y">{profiles.map((x) => <li key={x.id} className="py-2">{x.fullName}</li>)}</ul> : <p className="muted">Add the person who will receive care.</p>}
          <AddPatientForm />
        </div>
        <div className="card space-y-3">
          <h2 className="h2">Addresses</h2>
          {addresses.length ? <ul className="divide-y">{addresses.map((a) => <li key={a.id} className="py-2 text-sm"><b>{a.label ?? "Address"}</b> — {a.line1}, {a.locality}, {a.city} {a.pincode}</li>)}</ul> : <p className="muted">No saved addresses yet.</p>}
          <AddAddressForm />
        </div>
      </section>
      <section className="space-y-3">
        <h2 className="h2">Appointments</h2>
        {appts.length ? (
          <ul className="space-y-2">{appts.map((a) => (
            <li key={a.id}><Link href={`/patient/appointments/${a.id}`} className="card flex flex-wrap items-center justify-between gap-2 hover:border-brand-500">
              <span><b>{a.service.name}</b> for {a.patient.fullName} with {a.nurse.displayName}<br /><span className="muted">{formatInTz(a.startAt)} · {a.reference}</span></span>
              <StatusBadge status={a.status} />
            </Link></li>
          ))}</ul>
        ) : <Empty title="No appointments yet"><Link className="text-brand-700 underline" href="/patient/book">Book your first visit</Link></Empty>}
      </section>
      <section className="space-y-3">
        <h2 className="h2">Stays</h2>
        {stays.length ? <ul className="space-y-2">{stays.map((s) => <li key={s.id} className="card flex justify-between"><span><b>{s.unit.property.name}</b><br /><span className="muted">{s.checkIn.toISOString().slice(0, 10)} → {s.checkOut.toISOString().slice(0, 10)} · {s.reference}</span></span><StatusBadge status={s.status} /></li>)}</ul> : <Empty title="No stays booked"><Link className="text-brand-700 underline" href="/stays">Find a stay near a hospital</Link></Empty>}
      </section>
    </div>
  );
}
