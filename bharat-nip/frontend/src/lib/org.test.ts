import { describe, expect, it } from "vitest";

import { layoutTree, lifecycleReached } from "./org";

describe("organization helpers", () => {
  it("lays out a tree with parents centered over children", () => {
    const nodes = [
      { id: "root", manager: null },
      { id: "b", manager: "root" },
      { id: "a", manager: "root" },
      { id: "a1", manager: "a" },
      { id: "a2", manager: "a" },
    ];
    const pos = layoutTree(nodes, { columnWidth: 10, rowHeight: 100 });
    expect(pos.a1).toEqual({ x: 0, y: 200 });
    expect(pos.a2).toEqual({ x: 10, y: 200 });
    expect(pos.a).toEqual({ x: 5, y: 100 });
    expect(pos.b).toEqual({ x: 20, y: 100 });
    expect(pos.root).toEqual({ x: 12.5, y: 0 });
    expect(layoutTree([...nodes].reverse(), { columnWidth: 10, rowHeight: 100 })).toEqual(pos);
  });

  it("counts lifecycle stages from the execution log", () => {
    const r = lifecycleReached([{ kind: "DELEGATION" }, { kind: "EXECUTION" }, { kind: "REVIEW" }, { kind: "REVIEW" }]);
    expect(r).toMatchObject({ DELEGATION: 1, EXECUTION: 1, REVIEW: 2, REVISION: 0, APPROVAL: 0, COMPLETION: 0 });
  });
});
