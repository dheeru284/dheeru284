"""Thin wrapper around the Claude API returning schema-validated JSON."""
import json
import os

import anthropic

_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class Refused(Exception):
    pass


def json_call(model, system, prompt, schema, max_tokens=16000, effort="medium"):
    resp = client().beta.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
    )
    if resp.stop_reason == "refusal":
        raise Refused(str(getattr(resp, "stop_details", "")))
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def fake_enabled():
    return os.environ.get("AUTOPILOT_FAKE_LLM") == "1"
