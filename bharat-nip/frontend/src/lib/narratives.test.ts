import { describe, expect, it } from "vitest";

import { burstCount, evidenceTone, layoutGraph, recommendationTone, type GraphNode } from "./narratives";

function node(id: string, topic: string | null, momentum = 0): GraphNode {
  return {
    id,
    title: id,
    status: "EMERGING",
    topic_id: topic,
    topic_label: topic,
    claim_count: 2,
    recommendation: "MONITOR",
    evidence_status: "PENDING_VERIFICATION",
    momentum,
  };
}

describe("narrative helpers", () => {
  it("lays out one column per topic, ordered by momentum, deterministically", () => {
    const nodes = [node("b", "roads", 0.2), node("a", "roads", 0.9), node("c", "health"), node("d", null)];
    const pos = layoutGraph(nodes, { columnWidth: 100, rowHeight: 10 });
    expect(pos.c).toEqual({ x: 0, y: 0 }); // "health" column first
    expect(pos.a).toEqual({ x: 100, y: 0 }); // higher momentum on top
    expect(pos.b).toEqual({ x: 100, y: 10 });
    expect(pos.d).toEqual({ x: 200, y: 0 }); // no topic last
    expect(layoutGraph([...nodes].reverse(), { columnWidth: 100, rowHeight: 10 })).toEqual(pos);
  });

  it("maps recommendations and evidence statuses to tones", () => {
    expect(recommendationTone("ESCALATE")).toBe("destructive");
    expect(recommendationTone("IGNORE")).toBe("outline");
    expect(evidenceTone("VERIFIED_FALSE")).toBe("destructive");
    expect(evidenceTone("PENDING_VERIFICATION")).toBe("outline");
  });

  it("counts bursts", () => {
    const h = (burst: number) => ({ burst }) as never;
    expect(burstCount([h(1), h(1), h(2)])).toBe(2);
    expect(burstCount([])).toBe(0);
  });
});
