"use client";

import { useActionState, useState } from "react";

import type { ActionState } from "@/app/actions";
import { createTask, taskDecision } from "@/app/org-actions";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { humanize } from "@/lib/format";

function Feedback({ state }: { state: ActionState }) {
  if (state?.error) return <Alert tone="error">{state.error}</Alert>;
  if (state?.ok) return <Alert tone="success">{state.ok}</Alert>;
  return null;
}

const WORKFLOWS = [
  { value: "CLAIM_INVESTIGATION", field: "claim_id", hint: "Research, source verification, context and fact-check brief for one claim." },
  { value: "SUBMISSION_FACT_CHECK", field: "submission_id", hint: "Run extraction and the evidence pipeline for a submission; verdicts still go to human review." },
  { value: "MEDIA_CHECK", field: "submission_id", hint: "File facts and reuse of uploaded media (no manipulation detection)." },
  { value: "NARRATIVE_RESPONSE", field: "narrative_id", hint: "Strategy, draft, translations and compliance check; a reviewer must approve. Nothing is published." },
  { value: "ANALYTICS_REPORT", field: null, hint: "Aggregate statistics." },
] as const;

const LANGUAGES: Record<string, string> = {
  hi: "Hindi", bn: "Bengali", ta: "Tamil", te: "Telugu", mr: "Marathi", gu: "Gujarati",
  kn: "Kannada", ml: "Malayalam", pa: "Punjabi", ur: "Urdu", or: "Odia", as: "Assamese",
};

export function CreateTaskForm() {
  const [state, action, pending] = useActionState(createTask, undefined);
  const [workflow, setWorkflow] = useState<string>("CLAIM_INVESTIGATION");
  const wf = WORKFLOWS.find((w) => w.value === workflow)!;
  return (
    <form action={action} className="grid gap-4">
      <Label>
        Workflow
        <Select name="workflow" value={workflow} onChange={(e) => setWorkflow(e.target.value)}>
          {WORKFLOWS.map((w) => (
            <option key={w.value} value={w.value}>
              {humanize(w.value)}
            </option>
          ))}
        </Select>
      </Label>
      <p className="text-xs text-muted-foreground">{wf.hint}</p>
      {wf.field && (
        <Label>
          {humanize(wf.field)}
          <Input name={wf.field} required placeholder="UUID" />
        </Label>
      )}
      {workflow === "NARRATIVE_RESPONSE" && (
        <fieldset className="grid gap-2">
          <legend className="text-sm font-medium">Translate into (optional)</legend>
          <div className="flex flex-wrap gap-2">
            {Object.entries(LANGUAGES).map(([code, name]) => (
              <label key={code} className="flex items-center gap-1 rounded border px-2 py-1 text-xs">
                <input type="checkbox" name="languages" value={code} /> {name}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      {workflow === "ANALYTICS_REPORT" && (
        <Label>
          Window (days)
          <Input name="window_days" type="number" min={1} max={365} defaultValue={30} />
        </Label>
      )}
      <Feedback state={state} />
      <div>
        <Button type="submit" disabled={pending}>
          {pending ? "Running…" : "Create task"}
        </Button>
      </div>
    </form>
  );
}

export function TaskActions({
  taskId,
  status,
  canReview,
  isCreator,
  revisableSteps,
}: {
  taskId: string;
  status: string;
  canReview: boolean;
  isCreator: boolean;
  revisableSteps: string[];
}) {
  const [state, action, pending] = useActionState(taskDecision, undefined);
  const [choice, setChoice] = useState("");
  const options: { value: string; label: string }[] = [];
  if (status === "AWAITING_APPROVAL" && canReview && !isCreator) options.push({ value: "approve", label: "Approve" });
  if (["AWAITING_APPROVAL", "ESCALATED"].includes(status) && canReview && !isCreator) {
    if (revisableSteps.length) options.push({ value: "revise", label: "Request revision" });
    options.push({ value: "reject", label: "Reject" });
  }
  if (status === "ESCALATED") options.push({ value: "retry", label: "Retry escalated step (once)" });
  if (!["COMPLETED", "REJECTED", "CANCELLED", "FAILED"].includes(status)) options.push({ value: "cancel", label: "Cancel" });
  if (options.length === 0) return null;
  const selected = choice || options[0].value;
  return (
    <form action={action} className="grid gap-3">
      <input type="hidden" name="task_id" value={taskId} />
      {isCreator && status === "AWAITING_APPROVAL" && (
        <Alert tone="warning">You created this task, so another reviewer must approve or reject it (four-eyes rule).</Alert>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <Label>
          Action
          <Select name="action" value={selected} onChange={(e) => setChoice(e.target.value)}>
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Label>
        {selected === "revise" && (
          <Label>
            Step to revise
            <Select name="step_key">
              {revisableSteps.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </Label>
        )}
      </div>
      <Label>
        Notes {selected === "approve" ? "(optional)" : "(required)"}
        <Textarea name="notes" required={selected !== "approve"} />
      </Label>
      <Feedback state={state} />
      <div>
        <Button type="submit" disabled={pending}>
          Submit
        </Button>
      </div>
    </form>
  );
}
