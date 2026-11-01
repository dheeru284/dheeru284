"""Loads scripted responses for the mock LLM and mock search providers from a JSON file
(BNIP_MOCK_FIXTURES_PATH). Used for local demos and manual end-to-end runs with a real
worker. Settings refuse fixtures in production; every output is still labelled "mock".

Format:
{
  "llm": [{"prompt_id": "claim_extractor", "when_contains": "...", "reusable": true,
           "response": {...}}],
  "search": [{"when_contains": "literacy", "hits": [{"title": ..., "url": ..., ...}]}]
}
"""

from __future__ import annotations

import json
from pathlib import Path

from app.providers.llm.mock import MockLLMProvider, contains
from app.providers.search.base import SearchHit
from app.providers.search.mock import MockSearchProvider


def load_fixtures(path: Path, llm: MockLLMProvider | None, search: MockSearchProvider | None):
    data = json.loads(path.read_text(encoding="utf-8"))
    if llm is not None:
        for item in data.get("llm", []):
            response = item["response"]
            text = response if isinstance(response, str) else json.dumps(response)
            when = contains(item["when_contains"]) if item.get("when_contains") else None
            llm.script(item["prompt_id"], text, when=when, reusable=item.get("reusable", True))
    if search is not None:
        for item in data.get("search", []):
            hits = [SearchHit.model_validate(h) for h in item.get("hits", [])]
            search.script(hits, when_contains=item.get("when_contains"))
