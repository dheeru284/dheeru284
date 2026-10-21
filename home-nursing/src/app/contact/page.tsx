import Link from "next/link";
import { Prose } from "@/components/Prose";
export default function Page() {
  return <Prose title="Contact and support"><p>Signed-in users can raise a support request, complaint or safety concern from <Link className="text-brand-700 underline" href="/account">your account</Link>. For emergencies call 112.</p><p className="muted">Support phone and email will be published before launch.</p></Prose>;
}
