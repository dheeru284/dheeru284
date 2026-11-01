"use client";

import { useActionState } from "react";

import type { ActionState } from "@/app/actions";
import { addObservation, addResponse, analyzeNarratives, assessHarm, changeStatus } from "@/app/narrative-actions";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { humanize } from "@/lib/format";
import { HARM_CATEGORIES, HARM_SEVERITIES, OBSERVATION_METRICS, RESPONSE_TYPES } from "@/lib/narratives";

function Feedback({ state }: { state: ActionState }) {
  if (state?.error) return <Alert tone="error">{state.error}</Alert>;
  if (state?.ok) return <Alert tone="success">{state.ok}</Alert>;
  return null;
}

export function AnalyzeButton() {
  const [state, action, pending] = useActionState(analyzeNarratives, undefined);
  return (
    <form action={action} className="flex flex-wrap items-center gap-2">
      <Button type="submit" variant="outline" size="sm" disabled={pending}>
        {pending ? "Running…" : "Run analysis now"}
      </Button>
      <Feedback state={state} />
    </form>
  );
}

export function StatusForm({ narrativeId, allowed, suggested }: { narrativeId: string; allowed: string[]; suggested: string | null }) {
  const [state, action, pending] = useActionState(changeStatus, undefined);
  if (allowed.length === 0) return null;
  return (
    <form action={action} className="grid gap-3">
      <input type="hidden" name="narrative_id" value={narrativeId} />
      <Label>
        New status
        <Select name="status" defaultValue={allowed.includes(suggested ?? "") ? suggested! : allowed[0]}>
          {allowed.map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
              {s === suggested ? " (suggested)" : ""}
            </option>
          ))}
        </Select>
      </Label>
      <Label>
        Note (required)
        <Textarea name="note" required minLength={3} placeholder="Why is the status changing?" />
      </Label>
      <Feedback state={state} />
      <div>
        <Button type="submit" disabled={pending}>
          Change status
        </Button>
      </div>
    </form>
  );
}

export function HarmForm({ narrativeId, category, severity }: { narrativeId: string; category: string; severity: string }) {
  const [state, action, pending] = useActionState(assessHarm, undefined);
  return (
    <form action={action} className="grid gap-3">
      <input type="hidden" name="narrative_id" value={narrativeId} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Label>
          Category
          <Select name="category" defaultValue={category}>
            {HARM_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {humanize(c)}
              </option>
            ))}
          </Select>
        </Label>
        <Label>
          Severity
          <Select name="severity" defaultValue={severity}>
            {HARM_SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </Select>
        </Label>
      </div>
      <Label>
        Rationale (required for low or above)
        <Textarea name="rationale" placeholder="Real-world consequence: health, safety, voting mechanics, violence, fraud." />
      </Label>
      <Feedback state={state} />
      <div>
        <Button type="submit" variant="outline" disabled={pending}>
          Save harm assessment
        </Button>
      </div>
    </form>
  );
}

export function ObservationForm({ narrativeId }: { narrativeId: string }) {
  const [state, action, pending] = useActionState(addObservation, undefined);
  return (
    <form action={action} className="grid gap-3">
      <input type="hidden" name="narrative_id" value={narrativeId} />
      <p className="text-xs text-muted-foreground">
        Aggregate public counts only (for example, total views on a public post). Never record individual people or accounts.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Label>
          Channel
          <Input name="channel" required placeholder="e.g. video-site, news" />
        </Label>
        <Label>
          Metric
          <Select name="metric" defaultValue="VIEWS">
            {OBSERVATION_METRICS.map((m) => (
              <option key={m} value={m}>
                {humanize(m)}
              </option>
            ))}
          </Select>
        </Label>
        <Label>
          Value
          <Input name="value" type="number" min={0} required />
        </Label>
        <Label>
          Observed at
          <Input name="observed_at" type="datetime-local" />
        </Label>
        <Label className="sm:col-span-2">
          Source URL
          <Input name="source_url" type="url" />
        </Label>
      </div>
      <Feedback state={state} />
      <div>
        <Button type="submit" variant="outline" disabled={pending}>
          Record observation
        </Button>
      </div>
    </form>
  );
}

export function ResponseForm({ narrativeId }: { narrativeId: string }) {
  const [state, action, pending] = useActionState(addResponse, undefined);
  return (
    <form action={action} className="grid gap-3">
      <input type="hidden" name="narrative_id" value={narrativeId} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Label>
          Type
          <Select name="response_type" defaultValue="FACT_CHECK">
            {RESPONSE_TYPES.map((t) => (
              <option key={t} value={t}>
                {humanize(t)}
              </option>
            ))}
          </Select>
        </Label>
        <Label>
          Published at
          <Input name="published_at" type="datetime-local" />
        </Label>
        <Label className="sm:col-span-2">
          Title
          <Input name="title" required />
        </Label>
        <Label>
          URL
          <Input name="url" type="url" />
        </Label>
        <Label>
          Channel
          <Input name="channel" />
        </Label>
      </div>
      <Feedback state={state} />
      <div>
        <Button type="submit" variant="outline" disabled={pending}>
          Record existing response
        </Button>
      </div>
    </form>
  );
}
