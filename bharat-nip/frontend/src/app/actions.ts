"use server";

import { refresh } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { API_PREFIX, apiBaseUrl } from "@/lib/api";
import { ApiError, TOKEN_COOKIE, api } from "@/lib/server-api";

export type ActionState = { error?: string; ok?: string } | undefined;

function text(form: FormData, key: string): string | undefined {
  const v = form.get(key);
  return typeof v === "string" && v.trim() ? v.trim() : undefined;
}

export async function login(_: ActionState, form: FormData): Promise<ActionState> {
  let res: Response;
  try {
    res = await fetch(`${apiBaseUrl()}${API_PREFIX}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: text(form, "email"), password: form.get("password") }),
      cache: "no-store",
    });
  } catch {
    return { error: "The backend is unreachable." };
  }
  if (!res.ok) return { error: "Invalid email or password." };
  const { access_token, expires_in } = (await res.json()) as { access_token: string; expires_in: number };
  (await cookies()).set(TOKEN_COOKIE, access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: expires_in,
  });
  redirect("/claims");
}

export async function logout(): Promise<void> {
  (await cookies()).delete(TOKEN_COOKIE);
  redirect("/login");
}

function buildSubmission(form: FormData): Record<string, unknown> {
  const type = text(form, "submission_type") ?? "TEXT";
  const body: Record<string, unknown> = { submission_type: type };
  for (const key of ["raw_text", "source_url", "title", "publisher_name", "context_note", "statement_date"]) {
    const v = text(form, key);
    if (v) body[key] = v;
  }
  if (type === "VIDEO_METADATA") {
    const video: Record<string, unknown> = { platform: text(form, "video_platform") ?? "" };
    for (const [field, key] of [
      ["video_url", "video_url"],
      ["title", "video_title"],
      ["description", "video_description"],
      ["uploader", "video_uploader"],
      ["transcript", "video_transcript"],
    ]) {
      const v = text(form, key);
      if (v) video[field] = v;
    }
    body.video = video;
  }
  return body;
}

export async function submitClaim(_: ActionState, form: FormData): Promise<ActionState> {
  const body = buildSubmission(form);
  const file = form.get("file");
  let id: string;
  try {
    if (body.submission_type === "IMAGE" || body.submission_type === "PDF") {
      if (!(file instanceof File) || file.size === 0) return { error: "Choose a file to upload." };
      const upload = new FormData();
      upload.set("file", file);
      upload.set("payload", JSON.stringify(body));
      const res = await api<{ submission: { id: string } }>("/submissions/upload", {
        method: "POST",
        form: upload,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      id = res.submission.id;
    } else {
      const res = await api<{ submission: { id: string } }>("/submissions", {
        method: "POST",
        json: body,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      id = res.submission.id;
    }
  } catch (err) {
    return { error: err instanceof ApiError ? err.detail : "Submission failed." };
  }
  redirect(`/submissions/${id}`);
}

export async function addTranscription(_: ActionState, form: FormData): Promise<ActionState> {
  const id = text(form, "submission_id");
  try {
    await api(`/submissions/${id}/transcription`, { method: "POST", json: { text: form.get("text") } });
  } catch (err) {
    return { error: err instanceof ApiError ? err.detail : "Could not save the transcription." };
  }
  refresh();
  return { ok: "Transcription saved; processing restarted." };
}

export async function decideReview(_: ActionState, form: FormData): Promise<ActionState> {
  const taskId = text(form, "task_id");
  const payload: Record<string, unknown> = { decision: text(form, "decision") };
  const finalClassification = text(form, "final_classification");
  if (finalClassification) payload.final_classification = finalClassification;
  const notes = text(form, "notes");
  if (notes) payload.notes = notes;
  try {
    await api(`/review-tasks/${taskId}/decision`, { method: "POST", json: payload });
  } catch (err) {
    return { error: err instanceof ApiError ? err.detail : "Decision failed." };
  }
  refresh();
  return { ok: "Decision recorded." };
}

export async function rerunResearch(_: ActionState, form: FormData): Promise<ActionState> {
  try {
    await api(`/claims/${text(form, "claim_id")}/research`, { method: "POST" });
  } catch (err) {
    return { error: err instanceof ApiError ? err.detail : "Could not restart research." };
  }
  refresh();
  return { ok: "Research restarted." };
}
