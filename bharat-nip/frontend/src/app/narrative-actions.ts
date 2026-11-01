"use server";

import { refresh } from "next/cache";

import type { ActionState } from "@/app/actions";
import { ApiError, api } from "@/lib/server-api";

function text(form: FormData, key: string): string | undefined {
  const v = form.get(key);
  return typeof v === "string" && v.trim() ? v.trim() : undefined;
}

async function run(fn: () => Promise<unknown>, ok: string): Promise<ActionState> {
  try {
    await fn();
  } catch (err) {
    return { error: err instanceof ApiError ? err.detail : "Request failed." };
  }
  refresh();
  return { ok };
}

export async function changeStatus(_: ActionState, form: FormData): Promise<ActionState> {
  return run(
    () =>
      api(`/narratives/${text(form, "narrative_id")}/status`, {
        method: "POST",
        json: { status: text(form, "status"), note: text(form, "note") ?? "" },
      }),
    "Status updated.",
  );
}

export async function assessHarm(_: ActionState, form: FormData): Promise<ActionState> {
  return run(
    () =>
      api(`/narratives/${text(form, "narrative_id")}/harm`, {
        method: "PUT",
        json: { category: text(form, "category"), severity: text(form, "severity"), rationale: text(form, "rationale") ?? null },
      }),
    "Harm assessment saved. Re-run analysis to update the recommendation.",
  );
}

export async function addObservation(_: ActionState, form: FormData): Promise<ActionState> {
  const observed = text(form, "observed_at");
  return run(
    () =>
      api(`/narratives/${text(form, "narrative_id")}/observations`, {
        method: "POST",
        json: {
          observed_at: observed ? new Date(observed).toISOString() : new Date().toISOString(),
          channel: text(form, "channel"),
          metric: text(form, "metric"),
          value: Number(text(form, "value") ?? "0"),
          source_url: text(form, "source_url") ?? null,
          note: text(form, "note") ?? null,
        },
      }),
    "Observation recorded.",
  );
}

export async function addResponse(_: ActionState, form: FormData): Promise<ActionState> {
  const published = text(form, "published_at");
  return run(
    () =>
      api(`/narratives/${text(form, "narrative_id")}/responses`, {
        method: "POST",
        json: {
          response_type: text(form, "response_type"),
          title: text(form, "title"),
          url: text(form, "url") ?? null,
          channel: text(form, "channel") ?? null,
          published_at: published ? new Date(published).toISOString() : new Date().toISOString(),
        },
      }),
    "Response recorded.",
  );
}

export async function analyzeNarratives(): Promise<ActionState> {
  return run(() => api("/narratives/analyze", { method: "POST" }), "Analysis started; refresh in a moment.");
}
