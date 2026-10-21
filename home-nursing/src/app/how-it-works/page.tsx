import { Prose } from "@/components/Prose";
export default function Page() {
  return (
    <Prose title="How it works">
      <h2>For patients and families</h2>
      <ul><li>Sign in with your mobile number and add the person who needs care.</li><li>Pick a service, address, date and time. We search verified nurses approved for that service, available at that time, and within the road travel-time limit.</li><li>Request a visit. The nurse accepts or declines; you are notified either way.</li><li>Services that need a prescription or clinician order stay on hold until the document is checked.</li><li>After the visit, review the nurse and see your visit record.</li></ul>
      <h2>Matching</h2>
      <p>We estimate driving time from the nurse&apos;s approved service area to your address for your appointment time. Straight-line distance is never used as a travel time. If an estimate is unavailable, we tell you rather than guess. The travel-time limit is set by the platform (initially 120 minutes) and is never silently extended.</p>
      <h2>For nurses</h2>
      <p>Register, add your council registration and qualifications, upload documents, choose services and set availability. You become bookable only after our team verifies your credentials.</p>
    </Prose>
  );
}
