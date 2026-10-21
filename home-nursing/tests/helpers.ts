import type { RoleKey } from "@prisma/client";
import { prisma } from "@/lib/db";
import { permissionsFor, ROLE_PERMISSIONS } from "@/lib/auth/rbac";
import type { Principal } from "@/lib/auth/session";
import { setProviders } from "@/lib/providers";
import type { RouteEstimate, RoutingProvider } from "@/lib/providers/routing";
import { MockSmsProvider } from "@/lib/providers/sms";
import { MockPaymentProvider } from "@/lib/providers/payments";
import { MockStorageProvider } from "@/lib/providers/storage";
import { zonedToUtc } from "@/lib/time";

export { prisma };

export async function resetDb() {
  const tables = await prisma.$queryRaw<{ tablename: string }[]>`SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> '_prisma_migrations'`;
  await prisma.$executeRawUnsafe(`TRUNCATE ${tables.map((t) => `"${t.tablename}"`).join(", ")} CASCADE`);
  for (const [key, perms] of Object.entries(ROLE_PERMISSIONS) as [RoleKey, string[]][]) {
    const role = await prisma.role.create({ data: { key, description: key } });
    for (const p of perms) {
      const perm = await prisma.permission.upsert({ where: { key: p }, create: { key: p, description: p }, update: {} });
      await prisma.rolePermission.create({ data: { roleId: role.id, permissionId: perm.id } });
    }
  }
}

/** Deterministic routing for tests: minutes are looked up per origin latitude. */
export class FakeRouting implements RoutingProvider {
  readonly name = "fake";
  calls: { departAt: Date }[] = [];
  constructor(public byLat: Record<string, number | null | "throw">) {}
  async estimate(o: { lat: number }, _d: unknown, departAt: Date): Promise<RouteEstimate | null> {
    this.calls.push({ departAt });
    const v = this.byLat[o.lat.toFixed(4)];
    if (v === "throw") throw new Error("provider down");
    if (v == null) return null;
    return { minutes: v, distanceKm: v * 0.5, provider: "fake", trafficAware: true, simulated: false };
  }
}

export function useFakes(routing: RoutingProvider) {
  const sms = new MockSmsProvider();
  const payments = new MockPaymentProvider();
  setProviders({ routing, sms, payments, storage: new MockStorageProvider() });
  return { sms, payments };
}

export async function makeUser(phone: string, roles: RoleKey[]): Promise<Principal> {
  const u = await prisma.user.create({ data: { phone, fullName: phone } });
  for (const r of roles) {
    const role = await prisma.role.findUniqueOrThrow({ where: { key: r } });
    await prisma.userRole.create({ data: { userId: u.id, roleId: role.id } });
  }
  return { userId: u.id, roles, permissions: permissionsFor(roles), sessionId: "test" };
}

export async function makeService(over: Partial<{ slug: string; isInvasive: boolean; clinicalReviewApproved: boolean; requiresPrescription: boolean; durationMinutes: number; requiredQualifications: string[] }> = {}) {
  const cat = await prisma.serviceCategory.upsert({ where: { slug: "c" }, create: { slug: "c", name: "c" }, update: {} });
  const svc = await prisma.nursingService.create({
    data: { slug: over.slug ?? "vitals", name: over.slug ?? "Vitals", description: "d", categoryId: cat.id, durationMinutes: over.durationMinutes ?? 60, basePriceInPaise: 50000, patientTypes: [], requiredQualifications: over.requiredQualifications ?? ["GNM"], equipment: [], preVisitInfo: [], documentationRequirements: [], isActive: true, isInvasive: over.isInvasive ?? false, clinicalReviewApproved: over.clinicalReviewApproved ?? false, requiresPrescription: over.requiresPrescription ?? false },
  });
  await prisma.serviceProtocol.create({ data: { serviceId: svc.id, version: 1, isActive: true, checklist: [{ key: "identity", label: "Identity confirmed", required: true }] } });
  return svc;
}

let nurseSeq = 0;
export async function makeNurse(serviceId: string, opts: { lat: number; lng?: number; gender?: "FEMALE" | "MALE"; status?: "APPROVED" | "PENDING_VERIFICATION"; credential?: "VERIFIED" | "PENDING" | "REJECTED"; docExpires?: Date; maxTravelMinutes?: number; days?: number[] } = { lat: 12.97 }) {
  nurseSeq++;
  const p = await makeUser(`+9198${String(nurseSeq).padStart(8, "0")}`, ["NURSE"]);
  const cred = opts.credential ?? "VERIFIED";
  const n = await prisma.nurseProfile.create({
    data: {
      userId: p.userId, displayName: `Nurse ${nurseSeq}`, gender: opts.gender ?? "FEMALE", languages: ["en"], yearsExperience: 5, status: opts.status ?? "APPROVED",
      qualifications: { create: { code: "GNM", verificationStatus: cred === "VERIFIED" ? "VERIFIED" : "PENDING" } },
      registrations: { create: { councilName: "Test Council", state: "Karnataka", registrationNumber: `T-${nurseSeq}`, status: cred } },
      documents: { create: [{ kind: "REGISTRATION_CERT", storageKey: "k", mimeType: "application/pdf", sizeBytes: 1, status: cred, expiresOn: opts.docExpires }, { kind: "ID_PROOF", storageKey: "k2", mimeType: "application/pdf", sizeBytes: 1, status: cred }] },
      serviceAreas: { create: { label: `Area ${nurseSeq}`, city: "Bengaluru", latitude: opts.lat, longitude: opts.lng ?? 77.6, maxTravelMinutes: opts.maxTravelMinutes } },
      availability: { create: (opts.days ?? [0, 1, 2, 3, 4, 5, 6]).map((d) => ({ dayOfWeek: d, startMinute: 8 * 60, endMinute: 20 * 60 })) },
      eligibilities: { create: { serviceId, status: "APPROVED" } },
    },
  });
  return { principal: p, nurse: n };
}

export async function makePatient(phone = "+919111111111") {
  const p = await makeUser(phone, ["PATIENT"]);
  const patient = await prisma.patientProfile.create({ data: { accountUserId: p.userId, fullName: "Test Patient", medicalNotes: "secret-note" } });
  const address = await prisma.patientAddress.create({ data: { userId: p.userId, line1: "1 Test St", city: "Bengaluru", state: "Karnataka", pincode: "560001", latitude: 12.95, longitude: 77.6 } });
  return { principal: p, patient, address };
}

/** A future Monday 10:00 IST. */
export const NOW = new Date("2026-11-01T00:00:00Z");
export const at = (time = "10:00", date = "2026-11-02") => zonedToUtc(date, time);
