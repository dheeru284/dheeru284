import { describe, expect, it } from "vitest";

import { classificationTone, humanize, isInFlight, percent, shortDate } from "./format";

describe("format helpers", () => {
  it("maps classifications to tones without colouring non-determinations as true/false", () => {
    expect(classificationTone("TRUE")).toBe("success");
    expect(classificationTone("FALSE")).toBe("destructive");
    expect(classificationTone("MISLEADING")).toBe("warning");
    expect(classificationTone("INSUFFICIENT_EVIDENCE")).toBe("outline");
    expect(classificationTone("OPINION")).toBe("secondary");
    expect(classificationTone(null)).toBe("secondary");
  });

  it("humanizes enum values", () => {
    expect(humanize("INSUFFICIENT_EVIDENCE")).toBe("Insufficient evidence");
    expect(humanize(null)).toBe("—");
  });

  it("formats numbers and dates defensively", () => {
    expect(percent(0.856)).toBe("86%");
    expect(percent(null)).toBe("—");
    expect(shortDate("2024-01-15T00:00:00Z")).toBe("2024-01-15");
    expect(shortDate("not a date")).toBe("unknown");
  });

  it("knows when the pipeline is still running", () => {
    expect(isInFlight("PROCESSING", [])).toBe(true);
    expect(isInFlight("PROCESSED", ["RESEARCHING"])).toBe(true);
    expect(isInFlight("PROCESSED", ["PENDING_REVIEW", "APPROVED"])).toBe(false);
    expect(isInFlight("NEEDS_TRANSCRIPTION", [])).toBe(false);
  });
});
