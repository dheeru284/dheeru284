"use client";

import { useActionState, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  type ActionState,
  addTranscription,
  decideReview,
  login,
  rerunResearch,
  submitClaim,
} from "@/app/actions";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { humanize } from "@/lib/format";
import { CLASSIFICATIONS, type Classification } from "@/lib/types";

function Feedback({ state }: { state: ActionState }) {
  if (state?.error) return <Alert tone="error">{state.error}</Alert>;
  if (state?.ok) return <Alert tone="success">{state.ok}</Alert>;
  return null;
}

export function LoginForm() {
  const [state, action, pending] = useActionState(login, undefined);
  return (
    <form action={action} className="grid max-w-sm gap-4">
      <Label>
        Email
        <Input name="email" type="email" autoComplete="username" required />
      </Label>
      <Label>
        Password
        <Input name="password" type="password" autoComplete="current-password" required />
      </Label>
      <Feedback state={state} />
      <Button type="submit" disabled={pending}>
        {pending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}

const TYPES = [
  { value: "TEXT", label: "Text claim", hint: "Paste a statement or post." },
  { value: "URL", label: "URL", hint: "We fetch the page and extract its text (public https pages only)." },
  { value: "ARTICLE", label: "Article", hint: "Paste an article's body and its details." },
  { value: "IMAGE", label: "Image", hint: "Upload an image. Without OCR on the server, add a transcription." },
  { value: "PDF", label: "PDF", hint: "Upload a PDF with a text layer, or add a transcription." },
  { value: "VIDEO_METADATA", label: "Video metadata", hint: "Video is never downloaded: give its metadata and any transcript." },
] as const;

export function SubmitForm() {
  const [state, action, pending] = useActionState(submitClaim, undefined);
  const [type, setType] = useState<string>("TEXT");
  const current = TYPES.find((t) => t.value === type)!;
  return (
    <form action={action} className="grid gap-5">
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium">What are you submitting?</legend>
        <div className="flex flex-wrap gap-2">
          {TYPES.map((t) => (
            <label
              key={t.value}
              className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm has-checked:border-primary has-checked:bg-muted"
            >
              <input
                type="radio"
                name="submission_type"
                value={t.value}
                checked={type === t.value}
                onChange={() => setType(t.value)}
                className="accent-current"
              />
              {t.label}
            </label>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{current.hint}</p>
      </fieldset>

      {(type === "URL" || type === "ARTICLE") && (
        <Label>
          {type === "URL" ? "Page URL" : "Article URL (optional)"}
          <Input name="source_url" type="url" placeholder="https://…" required={type === "URL"} />
        </Label>
      )}
      {type === "ARTICLE" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Label>
            Headline
            <Input name="title" />
          </Label>
          <Label>
            Publisher
            <Input name="publisher_name" />
          </Label>
        </div>
      )}
      {(type === "IMAGE" || type === "PDF") && (
        <Label>
          File
          <Input
            name="file"
            type="file"
            accept={type === "PDF" ? "application/pdf" : "image/png,image/jpeg,image/gif,image/webp"}
            required
          />
        </Label>
      )}
      {type === "VIDEO_METADATA" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Label>
            Platform
            <Input name="video_platform" required placeholder="e.g. a video site" />
          </Label>
          <Label>
            Video URL
            <Input name="video_url" type="url" />
          </Label>
          <Label>
            Title
            <Input name="video_title" />
          </Label>
          <Label>
            Uploader
            <Input name="video_uploader" />
          </Label>
          <Label className="sm:col-span-2">
            Description
            <Textarea name="video_description" />
          </Label>
          <Label className="sm:col-span-2">
            Transcript (if you have one)
            <Textarea name="video_transcript" className="min-h-32" />
          </Label>
        </div>
      )}
      {type !== "VIDEO_METADATA" && (
        <Label>
          {type === "TEXT"
            ? "Claim text"
            : type === "ARTICLE"
              ? "Article text"
              : type === "URL"
                ? "Fallback text (used only if the page cannot be fetched)"
                : "Transcription (optional; used if no machine-readable text is found)"}
          <Textarea name="raw_text" required={type === "TEXT" || type === "ARTICLE"} className="min-h-32" />
        </Label>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Label>
          Date the statement was made (optional)
          <Input name="statement_date" type="date" />
        </Label>
        <Label>
          Context note (optional)
          <Input name="context_note" />
        </Label>
      </div>
      <Feedback state={state} />
      <div>
        <Button type="submit" disabled={pending}>
          {pending ? "Submitting…" : "Submit for fact-checking"}
        </Button>
      </div>
    </form>
  );
}

export function TranscriptionForm({ submissionId }: { submissionId: string }) {
  const [state, action, pending] = useActionState(addTranscription, undefined);
  return (
    <form action={action} className="grid gap-3">
      <input type="hidden" name="submission_id" value={submissionId} />
      <Label>
        Transcribe the text exactly as it appears
        <Textarea name="text" required minLength={20} className="min-h-28" />
      </Label>
      <Feedback state={state} />
      <div>
        <Button type="submit" disabled={pending}>
          Save transcription
        </Button>
      </div>
    </form>
  );
}

export function ReviewForm({
  taskId,
  proposed,
  hasAssessment,
}: {
  taskId: string;
  proposed: Classification | null;
  hasAssessment: boolean;
}) {
  const [state, action, pending] = useActionState(decideReview, undefined);
  const [decision, setDecision] = useState(hasAssessment ? "APPROVE" : "NEEDS_MORE_RESEARCH");
  const [classification, setClassification] = useState<string>(proposed ?? "");
  const changed = decision === "APPROVE" && classification !== (proposed ?? "");
  const notesRequired = decision !== "APPROVE" || changed;
  return (
    <form action={action} className="grid gap-4">
      <input type="hidden" name="task_id" value={taskId} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Label>
          Decision
          <Select name="decision" value={decision} onChange={(e) => setDecision(e.target.value)}>
            {hasAssessment && <option value="APPROVE">Approve</option>}
            <option value="NEEDS_MORE_RESEARCH">Needs more research</option>
            <option value="REJECT">Reject</option>
          </Select>
        </Label>
        {decision === "APPROVE" && (
          <Label>
            Final classification
            <Select
              name="final_classification"
              value={classification}
              onChange={(e) => setClassification(e.target.value)}
            >
              {CLASSIFICATIONS.map((c) => (
                <option key={c} value={c}>
                  {humanize(c)}
                  {c === proposed ? " (proposed)" : ""}
                </option>
              ))}
            </Select>
          </Label>
        )}
      </div>
      <Label>
        Notes {notesRequired ? "(required)" : "(optional)"}
        <Textarea name="notes" required={notesRequired} placeholder="What did you check? What is missing?" />
      </Label>
      <Feedback state={state} />
      <div>
        <Button type="submit" disabled={pending}>
          {pending ? "Recording…" : "Record decision"}
        </Button>
      </div>
    </form>
  );
}

export function RerunResearchButton({ claimId }: { claimId: string }) {
  const [state, action, pending] = useActionState(rerunResearch, undefined);
  return (
    <form action={action} className="grid gap-2">
      <input type="hidden" name="claim_id" value={claimId} />
      <Feedback state={state} />
      <div>
        <Button type="submit" variant="outline" disabled={pending}>
          Re-run research and assessment
        </Button>
      </div>
    </form>
  );
}

/** Refreshes server data every few seconds while the pipeline is still working. */
export function AutoRefresh({ active, intervalMs = 3000 }: { active: boolean; intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(id);
  }, [active, intervalMs, router]);
  if (!active) return null;
  return <p className="text-xs text-muted-foreground">Pipeline running; this page refreshes automatically.</p>;
}
