"""Scripted mock LLM provider. TEST INFRASTRUCTURE ONLY.

It never invents output: it returns only responses that were explicitly scripted
for a ``prompt_id``, and raises ``MockResponseNotScripted`` otherwise.
Settings refuse this provider in production (see app/core/config.py).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.providers.base import ProviderHealth
from app.providers.llm.base import LLMRequest, LLMResponse, TokenUsage

Matcher = Callable[[LLMRequest], bool]
# A scripted response is fixed text, or a function of the request (still explicit test
# scripting: e.g. look up which passage label holds a known document).
Responder = str | Callable[[LLMRequest], str]


class MockResponseNotScripted(Exception):
    pass


@dataclass
class _Script:
    prompt_id: str
    response: Responder
    when: Matcher | None
    reusable: bool


def contains(fragment: str) -> Matcher:
    """Matcher: the rendered user message contains ``fragment``."""
    return lambda req: fragment in req.messages[-1].content


class MockLLMProvider:
    name = "mock"
    is_mock = True

    def __init__(self, model: str = "mock-scripted-v1") -> None:
        self.model = model
        self._scripts: list[_Script] = []
        self.calls: list[LLMRequest] = []

    def script(
        self,
        prompt_id: str,
        response_text: Responder,
        when: Matcher | None = None,
        reusable: bool = False,
    ) -> None:
        """Queue a response for ``prompt_id``. Non-reusable responses are used once, in
        order; reusable ones answer every matching call."""
        self._scripts.append(_Script(prompt_id, response_text, when, reusable))

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        for i, s in enumerate(self._scripts):
            if s.prompt_id == request.prompt_id and (s.when is None or s.when(request)):
                if not s.reusable:
                    del self._scripts[i]
                text = s.response(request) if callable(s.response) else s.response
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

    def calls_for(self, prompt_id: str) -> list[LLMRequest]:
        return [c for c in self.calls if c.prompt_id == prompt_id]

    def health(self) -> ProviderHealth:
        return ProviderHealth(ok=True, detail="Mock LLM provider (scripted test responses only)")
