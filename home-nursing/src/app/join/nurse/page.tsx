import Link from "next/link";
import { Prose } from "@/components/Prose";
export default function Page() {
  return (
    <Prose title="Join as a registered nurse">
      <p>You&apos;ll need: your State Nursing Council registration number and certificate, qualification details (GNM, B.Sc Nursing, etc.), and a government ID.</p>
      <ul><li>Set the services you&apos;re qualified for and your own prices.</li><li>Choose your working hours and how far you&apos;re willing to travel.</li><li>Accept only the visits you want.</li></ul>
      <p>You will be bookable only after your documents are verified.</p>
      <Link href="/login?as=NURSE&next=/nurse/profile" className="btn">Start registration</Link>
    </Prose>
  );
}
