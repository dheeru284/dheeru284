import type { Classification } from "./types";

type Tone = "success" | "warning" | "destructive" | "secondary" | "outline";

/** Visual tone per classification. Determinations get colour; non-determinations stay neutral. */
export function classificationTone(c: Classification | null | undefined): Tone {
  switch (c) {
    case "TRUE":
    case "MOSTLY_TRUE":
      return "success";
    case "MISLEADING":
    case "OUT_OF_CONTEXT":
      return "warning";
    case "FALSE":
      return "destructive";
    case "UNVERIFIED":
    case "INSUFFICIENT_EVIDENCE":
      return "outline";
    default:
      return "secondary";
  }
}

export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .toLowerCase()
    .split("_")
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

/** Confidence as a whole percentage. 0 is shown as "no determination" by callers. */
export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  return d.toISOString().slice(0, 10);
}

export function shortHash(hash: string | null | undefined, n = 10): string {
  return hash ? hash.slice(0, n) : "—";
}

const FINAL_SUBMISSION = new Set(["PROCESSED", "NO_CLAIMS", "NEEDS_TRANSCRIPTION", "FAILED"]);
const FINAL_CLAIM = new Set(["PENDING_REVIEW", "APPROVED", "REJECTED", "NEEDS_MORE_RESEARCH", "FAILED"]);

/** True while the backend is still working, so the page should poll for updates. */
export function isInFlight(submissionStatus: string, claimStatuses: string[]): boolean {
  if (!FINAL_SUBMISSION.has(submissionStatus)) return true;
  return claimStatuses.some((s) => !FINAL_CLAIM.has(s));
}
