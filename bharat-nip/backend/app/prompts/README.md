# Prompts

Versioned prompt templates live here as `<prompt_id>/<version>.md`
(for example `assessor/v1.md`). Format and rules:
[AI_AGENT_ARCHITECTURE.md §4](../../../AI_AGENT_ARCHITECTURE.md).

No prompts ship in Phase 0. The first ones (`claim_extractor/v1`,
`evidence_analyst/v1`, `assessor/v1`, `critic/v1`) arrive with their agents in Phase 1.

Never edit a released version in place: add `v2.md`. `ai_runs.prompt_sha256`
records the hash of the exact file that ran.
