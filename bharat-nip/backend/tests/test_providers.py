import json
import math

import httpx
import pytest

from app.core.config import Settings
from app.providers.base import ProviderError
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.embeddings.ollama import OllamaEmbeddingProvider
from app.providers.llm.base import ChatMessage, LLMProvider, LLMRequest
from app.providers.llm.mock import MockLLMProvider, MockResponseNotScripted
from app.providers.llm.ollama import OllamaLLMProvider
from app.providers.registry import build_embedding_provider, build_llm_provider


def req(prompt_id: str = "demo", **kw) -> LLMRequest:
    return LLMRequest(
        prompt_id=prompt_id, messages=[ChatMessage(role="user", content="hello")], **kw
    )


# --- mock LLM -------------------------------------------------------------------------


def test_mock_refuses_unscripted_calls():
    with pytest.raises(MockResponseNotScripted):
        MockLLMProvider().complete(req())


def test_mock_returns_each_scripted_response_once_in_order():
    m = MockLLMProvider()
    m.script("demo", "first")
    m.script("demo", "second")
    assert m.complete(req()).text == "first"
    assert m.complete(req()).text == "second"
    with pytest.raises(MockResponseNotScripted):
        m.complete(req())
    assert len(m.calls) == 3


def test_mock_matcher_selects_response():
    m = MockLLMProvider()
    m.script("demo", "for-bye", when=lambda r: "bye" in r.messages[-1].content)
    m.script("demo", "for-hello", when=lambda r: "hello" in r.messages[-1].content)
    assert m.complete(req()).text == "for-hello"


def test_mock_identifies_itself():
    m = MockLLMProvider()
    m.script("demo", "x")
    resp = m.complete(req())
    assert resp.provider == "mock"
    assert m.is_mock is True
    assert isinstance(m, LLMProvider)


# --- Ollama LLM (HTTP mocked at the transport layer) -------------------------------------


def ollama_with(handler) -> OllamaLLMProvider:
    return OllamaLLMProvider(
        "http://ollama.test", "llama3.1:8b", transport=httpx.MockTransport(handler)
    )


def test_ollama_complete_sends_schema_and_seed_and_parses_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "llama3.1:8b",
                "message": {"role": "assistant", "content": '{"ok": true}'},
                "prompt_eval_count": 12,
                "eval_count": 5,
            },
        )

    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    resp = ollama_with(handler).complete(req(response_schema=schema, seed=7))
    assert seen["path"] == "/api/chat"
    assert seen["body"]["format"] == schema
    assert seen["body"]["stream"] is False
    assert seen["body"]["options"]["seed"] == 7
    assert seen["body"]["options"]["temperature"] == 0.0
    assert resp.text == '{"ok": true}'
    assert resp.provider == "ollama"
    assert resp.usage.prompt_tokens == 12
    assert resp.usage.completion_tokens == 5


def test_ollama_http_error_raises_provider_error():
    p = ollama_with(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(ProviderError):
        p.complete(req())


def test_ollama_malformed_response_raises_provider_error():
    p = ollama_with(lambda r: httpx.Response(200, json={"unexpected": 1}))
    with pytest.raises(ProviderError):
        p.complete(req())


def test_ollama_health_reports_missing_model():
    p = ollama_with(lambda r: httpx.Response(200, json={"models": [{"name": "other:latest"}]}))
    h = p.health()
    assert not h.ok
    assert "not pulled" in h.detail


def test_ollama_health_ok_when_model_present():
    p = ollama_with(lambda r: httpx.Response(200, json={"models": [{"name": "llama3.1:8b"}]}))
    assert p.health().ok


def test_ollama_health_unreachable():
    def handler(request):
        raise httpx.ConnectError("refused")

    h = ollama_with(handler).health()
    assert not h.ok
    assert "unreachable" in h.detail


# --- embeddings --------------------------------------------------------------------------


def test_mock_embeddings_are_deterministic_unit_vectors():
    m = MockEmbeddingProvider(dimensions=768)
    a1, a2, b = m.embed(["alpha", "alpha", "beta"]).vectors
    assert a1 == a2
    assert a1 != b
    assert len(a1) == 768
    assert math.isclose(math.sqrt(sum(x * x for x in a1)), 1.0, rel_tol=1e-9)
    assert isinstance(m, EmbeddingProvider)


def test_ollama_embeddings_validate_shape():
    good = OllamaEmbeddingProvider(
        "http://ollama.test",
        "nomic-embed-text",
        dimensions=3,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
        ),
    )
    assert good.embed(["x"]).vectors == [[0.1, 0.2, 0.3]]

    wrong_dims = OllamaEmbeddingProvider(
        "http://ollama.test",
        "nomic-embed-text",
        dimensions=768,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
        ),
    )
    with pytest.raises(ProviderError, match="unexpected shape"):
        wrong_dims.embed(["x"])


# --- registry ----------------------------------------------------------------------------


def test_registry_builds_configured_providers():
    s = Settings(_env_file=None, env="test", llm_provider="mock", embedding_provider="mock")
    assert build_llm_provider(s).name == "mock"
    assert build_embedding_provider(s).dimensions == 768
    s2 = Settings(_env_file=None, env="test", llm_provider="ollama", embedding_provider="ollama")
    assert isinstance(build_llm_provider(s2), OllamaLLMProvider)
    assert isinstance(build_embedding_provider(s2), OllamaEmbeddingProvider)
