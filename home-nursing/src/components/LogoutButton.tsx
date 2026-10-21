"use client";
export function LogoutButton({ label = "Sign out" }: { label?: string }) {
  return <button className="text-sm text-ink-500 hover:underline" onClick={async () => { await fetch("/api/v1/auth/logout", { method: "POST" }); location.href = "/"; }}>{label}</button>;
}
