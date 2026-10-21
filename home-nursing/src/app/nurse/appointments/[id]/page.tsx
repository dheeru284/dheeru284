import { notFound } from "next/navigation";
import { requirePage } from "@/lib/page-auth";
import { getAppointmentFor } from "@/lib/domain/appointments";
import { AppError } from "@/lib/errors";
import { AppointmentView } from "@/components/AppointmentView";

export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const p = await requirePage("appointment.nurse", `/nurse/appointments/${id}`);
  const a = await getAppointmentFor(p, id).catch((e) => { if (e instanceof AppError) notFound(); throw e; });
  return <AppointmentView a={JSON.parse(JSON.stringify(a))} />;
}
