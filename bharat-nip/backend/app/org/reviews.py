"""Manager reviews: deterministic acceptance checks a manager applies to a direct report's
tool-based work. LLM-generated work is reviewed by the Critic Agent instead."""

from __future__ import annotations

from typing import Any

Verdict = tuple[str, list[dict[str, str]], str]  # (PASS|REVISE|ESCALATE, issues, summary)


def _issue(severity: str, description: str) -> dict[str, str]:
    return {"severity": severity, "description": description}


def review(agent_key: str, output: dict[str, Any]) -> Verdict:
    check = CHECKS.get(agent_key)
    return check(output) if check else ("PASS", [], "Output is schema-valid.")


def _extraction(o: dict[str, Any]) -> Verdict:
    status = o["submission_status"]
    if status == "NEEDS_TRANSCRIPTION":
        return (
            "ESCALATE",
            [
                _issue(
                    "HIGH",
                    "No machine-readable text; a person must transcribe "
                    "it. The system will not guess.",
                )
            ],
            "Needs transcription.",
        )
    if status == "FAILED":
        return (
            "ESCALATE",
            [_issue("HIGH", o.get("extraction_notes") or "Extraction failed.")],
            "Extraction failed.",
        )
    if status in ("RECEIVED", "PROCESSING"):
        return ("ESCALATE", [_issue("HIGH", "Extraction did not run.")], "Not processed.")
    return ("PASS", [], f"{len(o['claims'])} claim(s) extracted ({status}).")


def _research(o: dict[str, Any]) -> Verdict:
    stuck = [
        c["claim_id"]
        for c in o["claims"]
        if c["status"] in ("EXTRACTED", "RESEARCHING", "ASSESSING", "CRITIQUING")
    ]
    if stuck:
        return (
            "ESCALATE",
            [_issue("HIGH", f"Pipeline did not finish for {stuck}.")],
            "Research incomplete.",
        )
    return (
        "PASS",
        [],
        f"Research complete for {len(o['claims'])} claim(s); every claim is "
        "with human review or decided.",
    )


def _media(o: dict[str, Any]) -> Verdict:
    if not o.get("limitations"):
        return ("REVISE", [_issue("HIGH", "Limitations must be stated.")], "Missing limitations.")
    return ("PASS", [], "Findings stated with limitations.")


def _narrative(o: dict[str, Any]) -> Verdict:
    return (
        "PASS",
        [],
        f"Brief ready: recommendation {o['recommendation']}, "
        f"{len(o['facts'])} approved fact-check(s).",
    )


CHECKS = {
    "claim_extraction_agent": _extraction,
    "research_agent": _research,
    "media_forensics_agent": _media,
    "narrative_intelligence_agent": _narrative,
}
