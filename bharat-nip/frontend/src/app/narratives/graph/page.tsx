import { Suspense } from "react";

import { NarrativeGraph } from "@/components/app/narrative-graph";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { ApiError, api } from "@/lib/server-api";
import type { NarrativeGraph as Graph } from "@/lib/narratives";

async function Content() {
  let graph: Graph;
  try {
    graph = await api<Graph>("/narratives/graph");
  } catch (err) {
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load the graph."}</Alert>;
  }
  return <NarrativeGraph graph={graph} />;
}

export default function GraphPage() {
  return (
    <PageShell
      title="Narrative relationship graph"
      description="Columns are topics. Edges: similar wording, same topic, shared subject entity (never the speaker), shared evidence, and contradictions between verified narratives. Click a narrative to open it."
    >
      <Suspense fallback={<Loading />}>
        <Content />
      </Suspense>
    </PageShell>
  );
}
