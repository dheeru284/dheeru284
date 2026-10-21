import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-14">
      <section className="grid items-center gap-8 md:grid-cols-2">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink-900 sm:text-4xl">Verified nurses at home, matched by real travel time.</h1>
          <p className="mt-4 text-lg text-ink-500">Book registered nurses whose credentials we have checked, who are qualified for the service you need, and who can reach you within the configured travel-time limit for your appointment time.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/patient/book" className="btn">Find a nurse</Link>
            <Link href="/stays" className="btn-secondary">Stays near hospitals</Link>
          </div>
        </div>
        <ul className="card space-y-4">
          {[
            ["Credential checks", "Nursing council registration and ID are reviewed by our team before a nurse can be booked. Uploading a document is not the same as being verified."],
            ["Qualified for your service", "Nurses only appear for services matching their verified qualifications."],
            ["Road travel time, not distance", "We estimate driving time for your appointment slot and show nurses within the limit (initially 2 hours)."],
            ["Your data stays need-to-know", "Nurses see your address only after they accept. Property partners never see medical information."],
          ].map(([t, d]) => (
            <li key={t}><p className="font-semibold text-brand-700">{t}</p><p className="muted">{d}</p></li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className="h2 mb-4">How it works</h2>
        <ol className="grid gap-4 sm:grid-cols-4">
          {["Choose a service and time", "See eligible nearby nurses", "Request a visit — the nurse confirms", "Nurse visits, records notes, you review"].map((s, i) => (
            <li key={s} className="card"><span className="text-sm font-bold text-brand-600">Step {i + 1}</span><p className="mt-1">{s}</p></li>
          ))}
        </ol>
      </section>
      <section className="grid gap-4 sm:grid-cols-2">
        <div className="card"><h2 className="h2">Are you a registered nurse?</h2><p className="muted mt-1">Set your services, availability and travel range.</p><Link href="/join/nurse" className="btn mt-4">Join as a nurse</Link></div>
        <div className="card"><h2 className="h2">Run serviced apartments near hospitals?</h2><p className="muted mt-1">List furnished stays for patients&apos; families.</p><Link href="/join/partner" className="btn mt-4">List your property</Link></div>
      </section>
    </div>
  );
}
