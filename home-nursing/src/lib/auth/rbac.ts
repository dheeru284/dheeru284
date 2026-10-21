import type { RoleKey } from "@prisma/client";

/** Permission keys. Seeded into Role/Permission tables; this map is the source of truth. */
export const ROLE_PERMISSIONS: Record<RoleKey, string[]> = {
  PATIENT: ["patient.self", "appointment.book", "accommodation.book", "review.write", "support.write", "privacy.self"],
  NURSE: ["nurse.self", "appointment.nurse", "visit.record", "support.write", "privacy.self"],
  ACCOMMODATION_PARTNER: ["partner.self", "property.manage", "stay.partner", "support.write", "privacy.self"],
  SUPPORT_AGENT: ["admin.access", "support.manage", "complaint.manage", "appointment.view_ops", "authorization.review"],
  COMPLIANCE_OFFICER: ["admin.access", "compliance.manage", "privacy.manage", "audit.read", "nurse.verify"],
  // Admin does NOT get clinical.read — clinical records need an explicit, audited break-glass grant.
  ADMIN: [
    "admin.access",
    "nurse.verify",
    "nurse.suspend",
    "catalog.manage",
    "settings.write",
    "flags.write",
    "hospital.manage",
    "property.verify",
    "complaint.manage",
    "support.manage",
    "appointment.view_ops",
    "payments.manage",
    "audit.read",
    "compliance.manage",
    "privacy.manage",
    "reports.export",
    "authorization.review",
    "users.manage",
    "reviews.moderate",
    "templates.manage",
    "locations.manage",
    "partners.manage",
  ],
};

export function permissionsFor(roles: RoleKey[]): Set<string> {
  return new Set(roles.flatMap((r) => ROLE_PERMISSIONS[r] ?? []));
}
