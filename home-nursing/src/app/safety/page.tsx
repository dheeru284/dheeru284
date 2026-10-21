import { Prose } from "@/components/Prose";
export default function Page() {
  return (
    <Prose title="Safety and emergencies">
      <p className="rounded-lg bg-alert-50 p-4 font-semibold text-alert-600">This is a non-emergency service. If someone has chest pain, difficulty breathing, severe bleeding, loss of consciousness, signs of stroke or any other emergency, call 112 immediately or go to the nearest emergency department.</p>
      <h2>What our nurses do and do not do</h2>
      <ul><li>Nurses perform services within their verified qualifications and approved scope.</li><li>Procedures that need a prescription or clinician order are carried out only against a valid document.</li><li>The app does not diagnose, prescribe, or recommend treatment. Observations recorded during a visit are for you and your doctor.</li></ul>
      <h2>Reporting a concern</h2>
      <p>Use “Report a safety concern” in your account or contact support. Serious complaints are reviewed by an administrator and may lead to suspension while investigated.</p>
    </Prose>
  );
}
