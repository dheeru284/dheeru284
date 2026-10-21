import Link from "next/link";
import { Prose } from "@/components/Prose";
export default function Page() {
  return (
    <Prose title="List your serviced apartment">
      <p>List furnished or serviced apartments near hospitals for patients&apos; families on short and long stays. Listings go live after verification.</p>
      <p>You will receive guest name, phone and dates for bookings — never any medical information.</p>
      <Link href="/login?as=ACCOMMODATION_PARTNER&next=/partner" className="btn">Register as a partner</Link>
    </Prose>
  );
}
