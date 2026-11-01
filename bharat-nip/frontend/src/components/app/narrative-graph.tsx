"use client";

import "@xyflow/react/dist/style.css";

import { Background, Controls, type Edge, MarkerType, type Node, ReactFlow } from "@xyflow/react";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { humanize } from "@/lib/format";
import { EDGE_COLORS, type NarrativeGraph as Graph, layoutGraph } from "@/lib/narratives";

export function NarrativeGraph({ graph, height = 560 }: { graph: Graph; height?: number }) {
  const router = useRouter();
  const { nodes, edges } = useMemo(() => {
    const pos = layoutGraph(graph.nodes);
    const nodes: Node[] = graph.nodes.map((n) => ({
      id: n.id,
      position: pos[n.id],
      data: {
        label: (
          <div className="grid gap-1 text-left">
            <span className="text-xs font-medium leading-snug">{n.title}</span>
            <span className="text-[10px] text-muted-foreground">
              {humanize(n.recommendation)} · {humanize(n.evidence_status)} · {n.claim_count} claims
            </span>
            {n.topic_label && <span className="text-[10px] text-muted-foreground">topic: {n.topic_label}</span>}
          </div>
        ),
      },
      style: {
        width: 240,
        borderRadius: 10,
        border: `2px solid ${n.recommendation === "ESCALATE" ? "#dc2626" : n.recommendation === "CORRECT" || n.recommendation === "INVESTIGATE" ? "#d97706" : "#d4d4d4"}`,
        background: "var(--card)",
        color: "var(--card-foreground)",
      },
    }));
    const edges: Edge[] = graph.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: humanize(e.type),
      labelStyle: { fontSize: 10 },
      style: {
        stroke: EDGE_COLORS[e.type] ?? "#9ca3af",
        strokeWidth: 1 + 2 * e.weight,
        strokeDasharray: e.type === "SAME_TOPIC" ? "4 4" : undefined,
      },
      markerEnd: e.type === "CONTRADICTS" ? { type: MarkerType.ArrowClosed, color: EDGE_COLORS.CONTRADICTS } : undefined,
    }));
    return { nodes, edges };
  }, [graph]);

  if (graph.nodes.length === 0) {
    return <p className="text-sm text-muted-foreground">No narratives detected yet.</p>;
  }
  return (
    <div className="grid gap-2">
      <div style={{ height }} className="w-full rounded-lg border">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          nodesConnectable={false}
          onNodeClick={(_, node) => router.push(`/narratives/${node.id}`)}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <ul className="flex flex-wrap gap-3 text-xs text-muted-foreground" aria-label="Edge legend">
        {Object.entries(EDGE_COLORS).map(([type, color]) => (
          <li key={type} className="flex items-center gap-1">
            <span className="inline-block h-0.5 w-5" style={{ background: color }} />
            {humanize(type)}
          </li>
        ))}
      </ul>
    </div>
  );
}
