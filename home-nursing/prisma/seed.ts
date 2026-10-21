/* Development seed. Every person, nurse, hospital and property here is FICTIONAL demo data (isDemo / "Demo" names).
 * Refuses to run in production. */
import { PrismaClient, type RoleKey } from "@prisma/client";
import { ROLE_PERMISSIONS } from "../src/lib/auth/rbac";
import { DEFAULT_TEMPLATES } from "../src/lib/domain/notifications";
import { DEFAULT_COMMERCE, DEFAULT_MATCHING } from "../src/lib/domain/settings";

const prisma = new PrismaClient();

export const SERVICES: { slug: string; name: string; cat: string; mins: number; price: number; quals?: string[]; rx?: boolean; invasive?: boolean; desc: string }[] = [
  { slug: "injection", name: "Injection administration", cat: "procedures", mins: 30, price: 499, rx: true, invasive: true, quals: ["GNM", "BSC_NURSING"], desc: "Administration of a prescribed injection." },
  { slug: "iv-fluids", name: "Intravenous fluid administration", cat: "procedures", mins: 120, price: 1499, rx: true, invasive: true, quals: ["GNM", "BSC_NURSING"], desc: "Prescribed IV fluid administration and monitoring." },
  { slug: "wound-care", name: "Wound dressing and wound care", cat: "procedures", mins: 45, price: 699, quals: ["GNM", "BSC_NURSING", "ANM"], desc: "Cleaning and dressing of wounds as per care plan." },
  { slug: "blood-sample", name: "Blood sample collection", cat: "procedures", mins: 30, price: 399, invasive: true, quals: ["GNM", "BSC_NURSING"], desc: "Sample collection for a partner laboratory (requires lab partner agreement)." },
  { slug: "health-check", name: "Home health check-up", cat: "monitoring", mins: 45, price: 599, quals: ["GNM", "BSC_NURSING", "ANM"], desc: "Basic observations recorded for your doctor. Not a diagnosis." },
  { slug: "vitals", name: "Vital signs monitoring", cat: "monitoring", mins: 30, price: 399, quals: ["GNM", "BSC_NURSING", "ANM"], desc: "Blood pressure, pulse, temperature and SpO2 observations." },
  { slug: "post-op", name: "Post-operative nursing care", cat: "care", mins: 90, price: 1199, quals: ["GNM", "BSC_NURSING"], desc: "Nursing support after surgery as per discharge instructions." },
  { slug: "elderly-care", name: "Elderly care and daily-living assistance", cat: "care", mins: 240, price: 1599, quals: ["GNM", "BSC_NURSING", "ANM"], desc: "Assistance with daily activities and monitoring." },
  { slug: "bedridden", name: "Bedridden patient care", cat: "care", mins: 240, price: 1799, quals: ["GNM", "BSC_NURSING"], desc: "Positioning, hygiene and pressure-area care." },
  { slug: "catheter", name: "Catheter care", cat: "procedures", mins: 45, price: 899, rx: true, invasive: true, quals: ["GNM", "BSC_NURSING"], desc: "Catheter care per clinician order." },
  { slug: "medication", name: "Medication administration (prescribed)", cat: "procedures", mins: 30, price: 449, rx: true, quals: ["GNM", "BSC_NURSING"], desc: "Administration of prescribed medicines only." },
  { slug: "assessment", name: "Basic nursing assessment", cat: "monitoring", mins: 60, price: 799, quals: ["GNM", "BSC_NURSING"], desc: "Nursing assessment shared with your doctor." },
  { slug: "chronic-support", name: "Chronic-condition nursing support", cat: "care", mins: 60, price: 899, quals: ["GNM", "BSC_NURSING"], desc: "Ongoing nursing support per your doctor's plan." },
  { slug: "palliative", name: "Palliative and supportive nursing", cat: "care", mins: 120, price: 1499, quals: ["GNM", "BSC_NURSING"], desc: "Comfort-focused nursing support." },
  { slug: "follow-up", name: "Follow-up nursing visit", cat: "monitoring", mins: 30, price: 449, quals: ["GNM", "BSC_NURSING", "ANM"], desc: "Follow-up visit after a previous nursing visit." },
  { slug: "care-package", name: "Recurring nursing visits", cat: "care", mins: 60, price: 799, quals: ["GNM", "BSC_NURSING"], desc: "Scheduled recurring visits (each visit checked for availability)." },
];

async function main() {
  if (process.env.NODE_ENV === "production") throw new Error("Refusing to seed demo data in production");

  // RBAC
  for (const [key, perms] of Object.entries(ROLE_PERMISSIONS) as [RoleKey, string[]][]) {
    const role = await prisma.role.upsert({ where: { key }, create: { key, description: key }, update: {} });
    for (const p of perms) {
      const perm = await prisma.permission.upsert({ where: { key: p }, create: { key: p, description: p }, update: {} });
      await prisma.rolePermission.upsert({ where: { roleId_permissionId: { roleId: role.id, permissionId: perm.id } }, create: { roleId: role.id, permissionId: perm.id }, update: {} });
    }
  }

  await prisma.platformSetting.upsert({ where: { key: "matching" }, create: { key: "matching", value: DEFAULT_MATCHING }, update: {} });
  await prisma.platformSetting.upsert({ where: { key: "commerce" }, create: { key: "commerce", value: DEFAULT_COMMERCE }, update: {} });

  const flags = [
    { key: "medicine_delivery", description: "FUTURE PHASE — requires pharmacy licensing & regulatory review. Locked off." },
    { key: "whatsapp_notifications", description: "WhatsApp channel via approved BSP" },
    { key: "recurring_visits", description: "Recurring nursing visits", enabled: true },
    { key: "accommodation", description: "Serviced apartment marketplace", enabled: true },
  ];
  for (const f of flags) await prisma.featureFlag.upsert({ where: { key: f.key }, create: { key: f.key, description: f.description, enabled: f.enabled ?? false }, update: {} });

  for (const [key, body] of Object.entries(DEFAULT_TEMPLATES))
    for (const channel of ["IN_APP", "SMS"]) await prisma.notificationTemplate.upsert({ where: { key_channel_language: { key, channel, language: "en" } }, create: { key, channel, language: "en", body }, update: {} });

  for (const c of [["Bengaluru", "Karnataka"], ["Mumbai", "Maharashtra"], ["Delhi", "Delhi"], ["Chennai", "Tamil Nadu"], ["Hyderabad", "Telangana"]])
    await prisma.city.upsert({ where: { name_state: { name: c[0]!, state: c[1]! } }, create: { name: c[0]!, state: c[1]! }, update: {} });

  // Catalog — invasive services remain unbookable until a clinician signs off (clinicalReviewApproved).
  const cats: Record<string, string> = {};
  for (const [slug, name] of [["procedures", "Nursing procedures"], ["monitoring", "Monitoring & check-ups"], ["care", "Ongoing care"]])
    cats[slug!] = (await prisma.serviceCategory.upsert({ where: { slug: slug! }, create: { slug: slug!, name: name! }, update: {} })).id;
  for (const s of SERVICES) {
    const svc = await prisma.nursingService.upsert({
      where: { slug: s.slug },
      create: {
        slug: s.slug, name: s.name, description: s.desc, categoryId: cats[s.cat]!, durationMinutes: s.mins, basePriceInPaise: s.price * 100, travelChargeInPaise: 0,
        patientTypes: ["adult", "elderly"], requiredQualifications: s.quals ?? [], requiresPrescription: !!s.rx, isInvasive: !!s.invasive, clinicalReviewApproved: false,
        equipment: [], preVisitInfo: s.rx ? ["Valid prescription or clinician order"] : [], documentationRequirements: ["visit_note"], isActive: true,
      },
      update: {},
    });
    if (s.rx) await prisma.serviceRequirement.deleteMany({ where: { serviceId: svc.id } }).then(() => prisma.serviceRequirement.create({ data: { serviceId: svc.id, kind: "PRESCRIPTION", description: "Upload a valid prescription or clinician order" } }));
    await prisma.serviceProtocol.upsert({
      where: { serviceId_version: { serviceId: svc.id, version: 1 } },
      create: {
        serviceId: svc.id, version: 1, isActive: true, // DRAFT checklist — must be reviewed by a qualified clinician before launch
        checklist: [
          { key: "identity_confirmed", label: "Patient identity confirmed", required: true },
          { key: "consent_obtained", label: "Verbal consent obtained", required: true },
          { key: "hand_hygiene", label: "Hand hygiene performed", required: true },
          { key: "waste_disposed", label: "Clinical waste handled per arrangement", required: false },
        ],
      },
      update: {},
    });
  }

  // Demo hospitals (fictional names; coordinates in real cities for routing).
  const hospitals = [
    { name: "Demo City General Hospital", address: "Demo Road, Indiranagar", city: "Bengaluru", state: "Karnataka", pincode: "560038", latitude: 12.9719, longitude: 77.6412 },
    { name: "Demo Lakeside Medical Centre", address: "Demo Avenue, Jayanagar", city: "Bengaluru", state: "Karnataka", pincode: "560041", latitude: 12.925, longitude: 77.5938 },
    { name: "Demo Harbour Hospital", address: "Demo Marg, Andheri", city: "Mumbai", state: "Maharashtra", pincode: "400053", latitude: 19.1197, longitude: 72.8464 },
  ];
  for (const h of hospitals) if (!(await prisma.hospital.findFirst({ where: { name: h.name } }))) await prisma.hospital.create({ data: { ...h, dataSource: "DEMO_SEED", specialties: [] } });

  // Users
  const mkUser = async (phone: string, fullName: string, roles: RoleKey[]) => {
    const u = await prisma.user.upsert({ where: { phone }, create: { phone, fullName }, update: {} });
    for (const r of roles) {
      const role = await prisma.role.findUniqueOrThrow({ where: { key: r } });
      await prisma.userRole.upsert({ where: { userId_roleId: { userId: u.id, roleId: role.id } }, create: { userId: u.id, roleId: role.id }, update: {} });
    }
    return u;
  };
  const admin = await mkUser("+919000000001", "Demo Admin", ["ADMIN"]);
  await mkUser("+919000000002", "Demo Compliance Officer", ["COMPLIANCE_OFFICER"]);
  const patientUser = await mkUser("+919000000010", "Demo Patient Family", ["PATIENT"]);
  const partnerUser = await mkUser("+919000000020", "Demo Stays Operator", ["ACCOMMODATION_PARTNER"]);

  if (!(await prisma.patientProfile.findFirst({ where: { accountUserId: patientUser.id } }))) {
    await prisma.patientProfile.create({ data: { accountUserId: patientUser.id, fullName: "Demo Grandparent", gender: "FEMALE" } });
    await prisma.patientAddress.create({ data: { userId: patientUser.id, label: "Home", line1: "12 Demo Street", locality: "Koramangala", city: "Bengaluru", state: "Karnataka", pincode: "560034", latitude: 12.9352, longitude: 77.6245 } });
  }

  // Demo nurses — fictional, flagged isDemo. Credentials are marked VERIFIED only so the dev flow works.
  const nurses = [
    { phone: "+919000000101", name: "Demo Nurse Asha", gender: "FEMALE" as const, lat: 12.9784, lng: 77.6408, area: "Indiranagar, Bengaluru", langs: ["en", "kn", "hi"], yrs: 8 },
    { phone: "+919000000102", name: "Demo Nurse Ravi", gender: "MALE" as const, lat: 12.9166, lng: 77.6101, area: "BTM Layout, Bengaluru", langs: ["en", "ta"], yrs: 4 },
    { phone: "+919000000103", name: "Demo Nurse Meera", gender: "FEMALE" as const, lat: 13.0358, lng: 77.597, area: "Hebbal, Bengaluru", langs: ["en", "ml", "hi"], yrs: 12 },
    { phone: "+919000000104", name: "Demo Nurse Far Away", gender: "FEMALE" as const, lat: 12.2958, lng: 76.6394, area: "Mysuru", langs: ["en", "kn"], yrs: 6 },
    { phone: "+919000000105", name: "Demo Nurse Pending", gender: "FEMALE" as const, lat: 12.95, lng: 77.62, area: "Ejipura, Bengaluru", langs: ["en"], yrs: 2, pending: true },
  ];
  const activeServices = await prisma.nursingService.findMany({ where: { isInvasive: false } });
  for (const n of nurses) {
    const u = await mkUser(n.phone, n.name, ["NURSE"]);
    if (await prisma.nurseProfile.findUnique({ where: { userId: u.id } })) continue;
    const status = n.pending ? "PENDING_VERIFICATION" : "APPROVED";
    const cred = n.pending ? "PENDING" : "VERIFIED";
    await prisma.nurseProfile.create({
      data: {
        userId: u.id, displayName: n.name, gender: n.gender, languages: n.langs, yearsExperience: n.yrs, status, isDemo: true, approvedAt: n.pending ? null : new Date(),
        bio: "Demo profile for development. Not a real nurse.",
        qualifications: { create: { code: "GNM", institution: "Demo Nursing School", verificationStatus: cred } },
        registrations: { create: { councilName: "Demo State Nursing Council", state: "Karnataka", registrationNumber: `DEMO-${n.phone.slice(-3)}`, status: cred as never } },
        documents: { create: [{ kind: "REGISTRATION_CERT", storageKey: `demo/${n.phone}/reg.pdf`, mimeType: "application/pdf", sizeBytes: 1000, status: cred as never }, { kind: "ID_PROOF", storageKey: `demo/${n.phone}/id.pdf`, mimeType: "application/pdf", sizeBytes: 1000, status: cred as never }] },
        serviceAreas: { create: { label: n.area, city: n.area.split(", ").pop()!, latitude: n.lat, longitude: n.lng } },
        availability: { create: [1, 2, 3, 4, 5, 6].map((d) => ({ dayOfWeek: d, startMinute: 8 * 60, endMinute: 20 * 60 })) },
        eligibilities: { create: activeServices.map((s) => ({ serviceId: s.id, status: n.pending ? "PENDING" : "APPROVED", approvedBy: n.pending ? null : admin.id, approvedAt: n.pending ? null : new Date() })) },
      },
    });
  }

  // Demo accommodation partner + properties
  const partner = await prisma.accommodationPartner.upsert({ where: { userId: partnerUser.id }, create: { userId: partnerUser.id, businessName: "Demo Stays Pvt (fictional)", verificationStatus: "VERIFIED" }, update: {} });
  const props = [
    { name: "Demo Serviced Suites Indiranagar", lat: 12.9735, lng: 77.6395, units: 2, nightly: 2500, monthly: 60000 },
    { name: "Demo Family Apartments Domlur", lat: 12.961, lng: 77.6387, units: 1, nightly: 1800, monthly: 42000 },
  ];
  for (const p of props) {
    if (await prisma.accommodationProperty.findFirst({ where: { name: p.name } })) continue;
    await prisma.accommodationProperty.create({
      data: {
        partnerId: partner.id, name: p.name, description: "Demo listing for development.", propertyType: "SERVICED_APARTMENT", address: "Demo address", city: "Bengaluru", state: "Karnataka", pincode: "560038",
        latitude: p.lat, longitude: p.lng, bedrooms: 2, bathrooms: 1, maxGuests: 4, accessibility: ["lift", "step_free_entry"], minStayNights: 2, cancellationPolicy: "Free cancellation up to 7 days before check-in.",
        verificationStatus: "VERIFIED", isDemo: true,
        units: { create: Array.from({ length: p.units }, (_, i) => ({ label: `Unit ${i + 1}` })) },
        amenities: { create: ["wifi", "kitchen", "washing_machine", "ac"].map((amenity) => ({ amenity })) },
        rates: { create: { nightlyInPaise: p.nightly * 100, monthlyInPaise: p.monthly * 100, extendedStayDiscountPct: 10, depositInPaise: 500000, validFrom: new Date("2000-01-01") } },
      },
    });
  }

  // Compliance registry — starter items, ALL pending legal review. Nothing here asserts applicability.
  const ci = [
    { jurisdiction: "IN", category: "Data protection", responsibleParty: "PLATFORM", requirement: "Digital Personal Data Protection Act, 2023 and Rules — notice, consent, grievance redressal, breach reporting, processor contracts", issuingAuthority: "MeitY / Data Protection Board of India" },
    { jurisdiction: "IN", category: "Cybersecurity", responsibleParty: "PLATFORM", requirement: "CERT-In directions (2022) on incident reporting and log retention", issuingAuthority: "CERT-In" },
    { jurisdiction: "IN", category: "Tax", responsibleParty: "PLATFORM", requirement: "GST registration and treatment of healthcare services / marketplace commission", issuingAuthority: "GSTN" },
    { jurisdiction: "KA", category: "Clinical establishment", responsibleParty: "PLATFORM", requirement: "Whether the operating model requires registration under the Karnataka Private Medical Establishments Act or other state framework", issuingAuthority: "Karnataka Health & Family Welfare Dept." },
    { jurisdiction: "KA", category: "Nurse registration", responsibleParty: "NURSE", requirement: "Valid registration with the State Nursing Council for each nurse practising in the state", issuingAuthority: "Karnataka State Nursing Council" },
    { jurisdiction: "IN", category: "Biomedical waste", responsibleParty: "CLINICAL_ESTABLISHMENT", requirement: "Bio-Medical Waste Management Rules, 2016 — arrangements for waste generated during home visits", issuingAuthority: "CPCB / SPCB" },
    { jurisdiction: "IN", category: "Laboratory partners", responsibleParty: "LAB_PARTNER", requirement: "Lab partner accreditation/registration for sample collection services", issuingAuthority: "State authority / NABL (voluntary)" },
    { jurisdiction: "KA", category: "Accommodation", responsibleParty: "ACCOMMODATION", requirement: "Local trade licence / registrations for serviced apartment operators", issuingAuthority: "Local municipal body" },
    { jurisdiction: "IN", category: "Payments", responsibleParty: "PAYMENT_TECH", requirement: "Payment aggregator terms; marketplace collection & settlement model review", issuingAuthority: "RBI-regulated PA" },
    { jurisdiction: "IN", category: "Insurance", responsibleParty: "PLATFORM", requirement: "Professional indemnity / general liability coverage for platform and nurses", issuingAuthority: "Insurer" },
  ];
  if ((await prisma.complianceItem.count()) === 0) for (const c of ci) await prisma.complianceItem.create({ data: { ...c, applicability: "PENDING_LEGAL_REVIEW", status: "OPEN", requiredDocuments: [] } });

  console.log("Seed complete (demo data).");
}

main().finally(() => prisma.$disconnect());
