import { notFound } from "next/navigation";
import { requirePage } from "@/lib/page-auth";
import { receiptFor } from "@/lib/domain/appointments";
import { AppError } from "@/lib/errors";
import { formatInTz } from "@/lib/time";
import { PrintButton } from "@/components/PrintButton";

export const dynamic = "force-dynamic";
const inr = (p: number) => `₹${(p / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

export default async function Receipt({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const p = await requirePage("patient.self", `/patient/appointments/${id}/receipt`);
  const r = await receiptFor(p, id).catch((e) => { if (e instanceof AppError) notFound(); throw e; });
  return (
    <div className="mx-auto max-w-2xl card space-y-4 print:border-0 print:shadow-none">
      <div className="flex items-start justify-between"><div><h1 className="h1">Receipt</h1><p className="muted">{r.receiptNo}</p></div><PrintButton /></div>
      <dl className="grid grid-cols-2 gap-2 text-sm">
        <dt className="muted">Booking</dt><dd>{r.reference}</dd>
        <dt className="muted">Service</dt><dd>{r.service}</dd>
        <dt className="muted">Patient</dt><dd>{r.patient}</dd>
        <dt className="muted">Nurse</dt><dd>{r.nurse}</dd>
        <dt className="muted">Visit</dt><dd>{formatInTz(r.visitAt)}</dd>
        <dt className="muted">Status</dt><dd>{r.status.toLowerCase().replaceAll("_", " ")}</dd>
        <dt className="muted">Visit charge</dt><dd className="font-semibold">{inr(r.amountInPaise)}</dd>
        <dt className="muted">Payment</dt><dd>{r.paymentStatus.toLowerCase()}</dd>
      </dl>
      {r.payments.map((x) => <p key={x.id} className="text-sm">Paid {inr(x.amountInPaise)} on {formatInTz(x.at)} (ref {x.id}){x.refunds.map((f, i) => <span key={i}> · refunded {inr(f.amountInPaise)} ({f.status.toLowerCase()})</span>)}</p>)}
      <p className="text-xs text-ink-500">{r.taxNote} This receipt is not a tax invoice.</p>
    </div>
  );
}
