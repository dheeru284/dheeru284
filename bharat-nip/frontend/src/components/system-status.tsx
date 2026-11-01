import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchSystemStatus } from "@/lib/api";

const CHECK_LABELS: Record<string, string> = {
  database: "PostgreSQL",
  pgvector: "pgvector extension",
  redis: "Redis (job broker)",
  llm_provider: "LLM provider",
  embedding_provider: "Embedding provider",
};

/** Live backend readiness. Rendered on every request; shows exactly what the API reports. */
export async function SystemStatus() {
  const status = await fetchSystemStatus();

  if (status.kind === "unreachable") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Backend <Badge variant="destructive">unreachable</Badge>
          </CardTitle>
          <CardDescription>
            Could not reach the API. Start it with <code>make dev-api</code>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="font-mono text-sm break-all text-muted-foreground">{status.error}</p>
        </CardContent>
      </Card>
    );
  }

  const { readiness, providers } = status;
  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Backend readiness
            <Badge variant={readiness.status === "ok" ? "success" : "warning"}>
              {readiness.status}
            </Badge>
          </CardTitle>
          <CardDescription>
            Live result of <code>GET /api/v1/health/ready</code> (HTTP {status.httpStatus}).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {Object.entries(readiness.checks).map(([name, check]) => (
              <li key={name} className="flex flex-wrap items-start justify-between gap-2 py-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{CHECK_LABELS[name] ?? name}</p>
                  <p className="text-xs break-words text-muted-foreground">{check.detail}</p>
                </div>
                <div className="flex shrink-0 gap-1">
                  {!check.required && <Badge variant="outline">optional here</Badge>}
                  <Badge variant={check.ok ? "success" : check.required ? "destructive" : "warning"}>
                    {check.ok ? "ok" : "failing"}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI providers</CardTitle>
          <CardDescription>
            Every AI output records its provider, model and prompt version.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm">
          <ProviderRow label="LLM" name={providers.llm.name} model={providers.llm.model} isMock={providers.llm.is_mock} />
          <ProviderRow
            label="Embeddings"
            name={providers.embedding.name}
            model={`${providers.embedding.model} (${providers.embedding.dimensions}d)`}
            isMock={providers.embedding.is_mock}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ProviderRow(props: { label: string; name: string; model: string; isMock: boolean }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-muted-foreground">{props.label}</span>
      <span className="flex items-center gap-2">
        <code className="break-all">
          {props.name} · {props.model}
        </code>
        {props.isMock && <Badge variant="warning">MOCK</Badge>}
      </span>
    </div>
  );
}

export function SystemStatusSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Backend readiness</CardTitle>
        <CardDescription>Checking…</CardDescription>
      </CardHeader>
    </Card>
  );
}
