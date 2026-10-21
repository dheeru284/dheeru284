"use client";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/client";
import { Alert, Field, useAction } from "@/components/ui";

const HOME: Record<string, string> = { PATIENT: "/patient", NURSE: "/nurse/profile", ACCOMMODATION_PARTNER: "/partner" };

export function LoginForm() {
  const sp = useSearchParams();
  const registerAs = (sp.get("as") ?? "PATIENT") as keyof typeof HOME;
  const [phone, setPhone] = useState("+91");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [challenge, setChallenge] = useState<{ challengeId: string; devCode?: string } | null>(null);
  const { busy, error, run } = useAction();

  return (
    <div className="mx-auto max-w-md card">
      <h1 className="h1">{registerAs === "NURSE" ? "Nurse sign in / register" : registerAs === "ACCOMMODATION_PARTNER" ? "Partner sign in / register" : "Sign in"}</h1>
      <p className="muted mt-1">We&apos;ll send a one-time code to your mobile.</p>
      <form
        className="mt-6 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            if (!challenge) setChallenge(await api("/auth/otp/request", { body: { phone } }));
            else {
              const me = await api<{ isNew: boolean }>("/auth/otp/verify", { body: { challengeId: challenge.challengeId, phone, code, registerAs, fullName: name || undefined } });
              const roles = (await api<{ roles: string[] }>("/auth/me")).roles;
              const next = sp.get("next");
              location.href = next && next.startsWith("/") ? next : roles.includes("ADMIN") || roles.includes("COMPLIANCE_OFFICER") ? "/admin" : HOME[roles[0] ?? "PATIENT"] ?? "/";
              void me;
            }
          });
        }}
      >
        <Field label="Mobile number" hint="Format: +91 followed by 10 digits">
          <input className="input" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value.replace(/[^\d+]/g, ""))} disabled={!!challenge} required />
        </Field>
        {challenge && (
          <>
            <Field label="6-digit code"><input className="input tracking-widest" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} required /></Field>
            <Field label="Your name (new accounts)"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
            {challenge.devCode && <Alert kind="warn">Development mode: your code is <b>{challenge.devCode}</b>. This is never shown in production.</Alert>}
          </>
        )}
        {error && <Alert>{error}</Alert>}
        <button className="btn w-full" disabled={busy}>{busy ? "Please wait…" : challenge ? "Verify and continue" : "Send code"}</button>
      </form>
    </div>
  );
}
