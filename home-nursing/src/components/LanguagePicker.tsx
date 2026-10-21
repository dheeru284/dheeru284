"use client";
import { LANGS } from "@/lib/i18n";

export function LanguagePicker({ current, signedIn }: { current: string; signedIn: boolean }) {
  return (
    <select aria-label="Language" className="rounded border border-slate-300 bg-white px-1 py-1 text-xs" value={current} onChange={async (e) => {
      const lang = e.target.value;
      document.cookie = `hn_lang=${lang}; path=/; max-age=31536000; samesite=lax`;
      if (signedIn) await fetch("/api/v1/account", { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ preferredLanguage: lang }) });
      location.reload();
    }}>
      {Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
    </select>
  );
}
