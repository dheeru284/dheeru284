"use client";
import { useRouter } from "next/navigation";
import { api } from "@/lib/client";

export function PauseToggle({ paused }: { paused: boolean }) {
  const r = useRouter();
  return (
    <button className={paused ? "btn" : "btn-secondary"} onClick={async () => {
      const me = await api<{ availability: { dayOfWeek: number; startMinute: number; endMinute: number }[] }>("/nurses/me");
      await api("/nurses/me/availability", { method: "PUT", body: { weekly: me.availability.map(({ dayOfWeek, startMinute, endMinute }) => ({ dayOfWeek, startMinute, endMinute })), isPaused: !paused } });
      r.refresh();
    }}>{paused ? "Paused — resume" : "Accepting — pause"}</button>
  );
}
