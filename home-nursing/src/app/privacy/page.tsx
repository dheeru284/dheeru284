import { Prose } from "@/components/Prose";
export default function Page() {
  return (
    <Prose title="Privacy policy" draft>
      <h2>What we collect and why</h2>
      <ul><li>Account: mobile number, name — to sign you in and contact you.</li><li>Care information you choose to share (e.g. allergies, notes) — only to deliver the booked visit, with your consent.</li><li>Addresses and location — to match nurses and guide the assigned nurse to you.</li><li>Payment status (we do not store card numbers or CVV).</li></ul>
      <h2>Who sees it</h2>
      <ul><li>Your assigned nurse sees your address and care notes only after accepting your booking.</li><li>Accommodation partners see only your name, phone and stay dates — never medical information.</li><li>Our staff access data on a need-to-know basis; sensitive access is logged.</li></ul>
      <h2>Your rights</h2>
      <p>From your account you can export your data, request correction or deletion, withdraw consent, and raise a grievance. Some records may need to be retained for legal reasons.</p>
    </Prose>
  );
}
