"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/app/actions";
import { ApiError, api } from "@/lib/server-api";

function text(form: FormData, key: string): string | undefined {
  const v = form.get(key);
  return typeof v === "string" && v.trim() ? v.trim() : undefined;
}

export async function createTask(_: ActionState, form: FormData): Promise<ActionState> {
  const workflow = text(form, "workflow");
  const input: Record<string, unknown> = {};
  for (const key of ["submission_id", "claim_id", "narrative_id"]) {
    const v = text(form, key);
    if (v) input[key] = v;
  }
  if (workflow === "NARRATIVE_RESPONSE") input.languages = form.getAll("languages").map(String);
  if (workflow === "ANALYTICS_REPORT") input.window_days = Number(text(form, "window_days") ?? "30");
  let id: string;
  try {
    id = (await api<{ id: string }>("/org/tasks", { method: "POST", json: { workflow, input } })).id;
  } catch (err) {
    return { error: err instanceof ApiError ? err.detail : "Could not create the task." };
  }
  redirect(`/tasks/${id}`);
}

async function act(path: string, json: unknown, ok: string): Promise<ActionState> {
  try {
    await api(path, { method: "POST", json });
  } catch (err) {
    return { error: err instanceof ApiError ? err.detail : "Request failed." };
  }
  refresh();
  return { ok };
}

export async function taskDecision(_: ActionState, form: FormData): Promise<ActionState> {
  const id = text(form, "task_id");
  const action = text(form, "action");
  const notes = text(form, "notes");
  switch (action) {
    case "approve":
      return act(`/org/tasks/${id}/approve`, { notes: notes ?? null }, "Approved.");
    case "reject":
      return act(`/org/tasks/${id}/reject`, { notes: notes ?? "" }, "Rejected.");
    case "revise":
      return act(`/org/tasks/${id}/request-revision`, { step_key: text(form, "step_key"), notes: notes ?? "" }, "Revision requested.");
    case "retry":
      return act(`/org/tasks/${id}/retry`, { notes: notes ?? "Retry." }, "Retried.");
    case "cancel":
      return act(`/org/tasks/${id}/cancel`, { notes: notes ?? "Cancelled." }, "Cancelled.");
    default:
      return { error: "Unknown action." };
  }
}
