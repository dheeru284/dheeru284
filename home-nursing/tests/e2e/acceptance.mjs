// End-to-end acceptance smoke test over HTTP. Requires: seeded dev DB, server running with DEV_EXPOSE_OTP=true.
// Usage: BASE_URL=http://localhost:3000 node tests/e2e/acceptance.mjs
const BASE = process.env.BASE_URL ?? "http://localhost:3000";
let failures = 0;
const check = (cond, msg) => { console.log(`${cond ? "✓" : "✗"} ${msg}`); if (!cond) failures++; };

function client() {
  let cookie = "";
  return async (path, body, method) => {
    const res = await fetch(`${BASE}/api/v1${path}`, { method: method ?? (body ? "POST" : "GET"), headers: { ...(body ? { "content-type": "application/json" } : {}), ...(cookie ? { cookie } : {}) }, body: body ? JSON.stringify(body) : undefined });
    const set = res.headers.get("set-cookie");
    if (set) cookie = set.split(";")[0];
    const json = await res.json().catch(() => ({}));
    return { status: res.status, ...json };
  };
}
async function login(phone, registerAs = "PATIENT") {
  const c = client();
  const { data } = await c("/auth/otp/request", { phone });
  const v = await c("/auth/otp/verify", { challengeId: data.challengeId, phone, code: data.devCode, registerAs });
  if (v.status !== 200) throw new Error(`login failed for ${phone}: ${JSON.stringify(v)}`);
  return c;
}
function nextWeekday(dow, minDays = 3) {
  const d = new Date(Date.now() + minDays * 86400000);
  while (d.getUTCDay() !== dow) d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

const date = nextWeekday(2); // Tuesday
const patient = await login("+919000000010");
const admin = await login("+919000000001");

// 1. Patient profile
const p = await patient("/patients", { fullName: `E2E Patient ${Date.now()}`, consentToCareDataProcessing: true });
check(p.status === 200, "patient registers and adds a patient profile");
const addresses = (await patient("/patients/addresses")).data;
const services = (await patient("/services")).data;
const vitals = services.find((s) => s.slug === "vitals");
check(!services.some((s) => s.slug === "injection"), "invasive services pending clinical review are not offered");

// 2–5. Matching
const time = `${String(9 + Math.floor(Math.random() * 8)).padStart(2, "0")}:${["00", "15", "30", "45"][Math.floor(Math.random() * 4)]}`;
const m = await patient("/matching", { serviceId: vitals.id, addressId: addresses[0].id, date, time });
check(m.status === 200 && m.data.appliedLimitMinutes === 120, "default travel-time limit is 120 minutes");
const names = m.data.results.map((r) => r.displayName);
check(!names.includes("Demo Nurse Pending"), "pending nurse is not bookable");
check(!names.includes("Demo Nurse Far Away"), "nurse beyond the travel limit is excluded");
check(m.data.results.length > 0 && m.data.results.every((r) => r.travel.minutes <= 120), "results have road travel estimates within the limit");
check(m.data.results.every((r, i, a) => i === 0 || a[i - 1].score >= r.score), "results are ranked");
check(!JSON.stringify(m.data).includes("latitude"), "nurse coordinates are not exposed");

// 6. Book
const pick = m.data.results[0];
const b = await patient("/appointments", { patientId: p.data.id, nurseId: pick.nurseId, serviceId: vitals.id, addressId: addresses[0].id, date, time });
check(b.status === 201 && b.data.status === "AWAITING_NURSE_ACCEPTANCE", `appointment requested (${b.data?.reference})`);
// 8. Double booking
const dup = await patient("/appointments", { patientId: p.data.id, nurseId: pick.nurseId, serviceId: vitals.id, addressId: addresses[0].id, date, time });
check(dup.status === 409, "double booking is rejected");

// 7. Nurse workflow
const phones = { "Demo Nurse Asha": "+919000000101", "Demo Nurse Ravi": "+919000000102", "Demo Nurse Meera": "+919000000103" };
const nurse = await login(phones[pick.displayName], "NURSE");
const before = await nurse(`/appointments/${b.data.id}`);
check(!before.data.address.line1, "nurse sees no street address before accepting");
for (const to of ["CONFIRMED", "NURSE_EN_ROUTE", "NURSE_ARRIVED", "IN_PROGRESS"]) await nurse(`/appointments/${b.data.id}/transition`, { to });
const view = await nurse(`/appointments/${b.data.id}`);
for (const item of view.data.visit.checklist) await nurse(`/visits/${b.data.id}/checklist`, { itemKey: item.itemKey, done: true });
await nurse(`/visits/${b.data.id}/notes`, { notes: "Observations recorded.", observations: { pulse: 78, spo2: 98 } });
const done = await nurse(`/appointments/${b.data.id}/transition`, { to: "COMPLETED" });
check(done.status === 200 && done.data.appointment.status === "COMPLETED", "nurse accepts and completes the visit workflow");

// 14. Isolation
const stranger = await login(`+9197${String(Date.now()).slice(-8)}`);
check((await stranger(`/appointments/${b.data.id}`)).status === 404, "another patient cannot see the appointment");
check((await patient("/admin/settings")).status === 403, "patient cannot access admin settings");
check((await nurse("/admin/nurses")).status === 403, "nurse cannot access verification queue");

// 16. Payment via dev adapter, verified server-side
const order = await patient("/payments/orders", { appointmentId: b.data.id });
const forged = await patient("/payments/confirm", { providerOrderId: order.data.providerOrderId, providerPaymentId: "pay_x", signature: "forged" });
check(forged.status === 400, "forged payment confirmation is rejected");
const paid = await patient("/payments/dev-simulate", { providerOrderId: order.data.providerOrderId });
check(paid.status === 200 && paid.data.status === "CAPTURED", "payment captured through development adapter with server-side verification");
check((await patient("/notifications")).data.length > 0, "patient received in-app notifications");

// 10. Admin threshold change
await admin("/admin/settings", { key: "matching", patch: { maxTravelMinutes: 15 } }, "PUT");
const m2 = await patient("/matching", { serviceId: vitals.id, addressId: addresses[0].id, date, time: "18:00" });
check(m2.data.appliedLimitMinutes === 15, "admin changed travel-time threshold without code changes");
await admin("/admin/settings", { key: "matching", patch: { maxTravelMinutes: 120 } }, "PUT");

// 11–13. Accommodation
const hospitals = (await patient("/hospitals?q=Demo%20City")).data;
check(hospitals.length > 0, "patient can search hospitals");
const ci = nextWeekday(1, 30 + Math.floor(Math.random() * 300)), co = new Date(Date.parse(ci) + 35 * 86400000).toISOString().slice(0, 10);
const stays = await patient(`/accommodations/search?hospitalId=${hospitals[0].id}&checkIn=${ci}&checkOut=${co}&guests=2`);
check(stays.status === 200 && stays.data.results.length > 0, "nearby stays found");
const single = stays.data.results.find((r) => r.freeUnits === 1);
if (single) {
  const s1 = await patient("/accommodation-bookings", { propertyId: single.id, checkIn: ci, checkOut: co, guests: 2, hospitalId: hospitals[0].id });
  check(s1.status === 201, `extended stay requested (${s1.data?.reference}, 35 nights)`);
  const s2 = await stranger("/accommodation-bookings", { propertyId: single.id, checkIn: ci, checkOut: co, guests: 1 });
  check(s2.status === 409, "conflicting accommodation reservation is rejected");
}
const partner = await login("+919000000020", "ACCOMMODATION_PARTNER");
check((await partner(`/appointments/${b.data.id}`)).status === 404, "accommodation partner cannot access nursing appointments");

// 15. Admin review surfaces
check((await admin("/admin/complaints")).status === 200 && (await admin("/compliance")).status === 200 && (await admin("/admin/nurses")).status === 200, "admin can review complaints, credentials and compliance");
// 19.
check((await patient("/medicine")).status === 403, "medicine delivery is disabled");
check((await admin("/admin/flags", { key: "medicine_delivery", enabled: true }, "PUT")).status === 403, "medicine delivery flag cannot be enabled");

console.log(failures ? `\n${failures} check(s) FAILED` : "\nAll acceptance checks passed");
process.exit(failures ? 1 : 0);
