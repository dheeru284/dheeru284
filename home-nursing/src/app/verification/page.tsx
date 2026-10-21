import { Prose } from "@/components/Prose";
export default function Page() {
  return (
    <Prose title="How nurse verification works">
      <ul>
        <li>Nurses submit their State Nursing Council registration number, qualification details, an identity document and registration certificate.</li>
        <li>Each document is reviewed by an authorised team member. Every decision (verified, rejected, revoked) and the reviewer are recorded.</li>
        <li>A nurse is listed only after mandatory credentials are verified and the account is approved.</li>
        <li>Each service requires a matching verified qualification and separate approval.</li>
        <li>Expired, revoked or rejected credentials automatically remove a nurse from search results.</li>
      </ul>
      <p className="muted">Verification is a document and registration check. It does not replace your own judgement or your doctor&apos;s advice.</p>
    </Prose>
  );
}
