import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({ permission: "admin.access" }, async () => {
  const [nursesPending, nursesApproved, apptByStatus, openComplaints, staysRequested, privacyOpen, gmv] = await Promise.all([
    prisma.nurseProfile.count({ where: { status: "PENDING_VERIFICATION" } }),
    prisma.nurseProfile.count({ where: { status: "APPROVED" } }),
    prisma.appointment.groupBy({ by: ["status"], _count: true }),
    prisma.complaint.count({ where: { status: { in: ["OPEN", "INVESTIGATING"] } } }),
    prisma.accommodationBooking.count({ where: { status: "REQUESTED" } }),
    prisma.privacyRequest.count({ where: { status: { in: ["RECEIVED", "IN_PROGRESS"] } } }),
    prisma.payment.aggregate({ where: { status: "CAPTURED" }, _sum: { amountInPaise: true } }),
  ]);
  return { nursesPending, nursesApproved, appointmentsByStatus: Object.fromEntries(apptByStatus.map((r) => [r.status, r._count])), openComplaints, staysRequested, privacyOpen, capturedInPaise: gmv._sum.amountInPaise ?? 0 };
});
