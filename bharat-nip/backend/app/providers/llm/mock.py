"""Scripted mock LLM provider. TEST INFRASTRUCTURE ONLY.

It never invents output: it returns only responses that were explicitly scripted
for a ``prompt_id``, and raises ``MockResponseNotScripted`` otherwise.
Settings refuse this provider in production (see app/core/config.py).
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable

from app.providers.base import ProviderHealth
from app.providers.llm.base import LLMRequest, LLMResponse, TokenUsage

Matcher = Callable[[LLMRequest], bool]


class MockResponseNotScripted(Exception):
    pass


class MockLLMProvider:
    name = "mock"
    is_mock = True

    def __init__(self, model: str = "mock-scripted-v1") -> None:
        self.model = model
        self._scripts: dict[str, deque[tuple[Matcher | None, str]]] = defaultdict(deque)
        self.calls: list[LLMRequest] = []

    def script(self, prompt_id: str, response_text: str, when: Matcher | None = None) -> None:
        """Queue a response for ``prompt_id``. Each scripted response is used once, in order."""
        self._scripts[prompt_id].append((when, response_text))

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        queue = self._scripts.get(request.prompt_id)
        if queue:
            for i, (matcher, text) in enumerate(queue):
                if matcher is None or matcher(request):
                    del queue[i]
                    return LLMResponse(
                        text=text,
                        provider=self.name,
                        model=self.model,
                        usage=TokenUsage(prompt_tokens=0, completion_tokens=0),
                        latency_ms=0,
                    )
        raise MockResponseNotScripted(
            f"No scripted mock response for prompt_id={request.prompt_id!r}"
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(ok=True, detail="Mock LLM provider (scripted test responses only)")
