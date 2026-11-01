from app.api import deps
from app.core.config import Settings


def test_liveness(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "0.2.0"}


def test_readiness_ok_with_real_db_and_redis(client):
    r = client.get("/api/v1/health/ready")
    body = r.json()
    assert r.status_code == 200, body
    assert body["status"] == "ok"
    assert set(body["checks"]) == {
        "database",
        "pgvector",
        "redis",
        "llm_provider",
        "embedding_provider",
    }
    assert body["checks"]["pgvector"]["ok"]
    assert body["checks"]["llm_provider"]["detail"].startswith("mock:")


def test_readiness_503_when_required_dependency_down(client):
    broken = Settings(
        _env_file=None,
        env="test",
        redis_url="redis://127.0.0.1:1/0",
        llm_provider="mock",
        embedding_provider="mock",
    )
    client.app.dependency_overrides[deps.get_settings_dep] = lambda: broken
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["checks"]["redis"]["ok"] is False


def test_providers_endpoint_flags_mock(client):
    r = client.get("/api/v1/system/providers")
    assert r.status_code == 200
    body = r.json()
    assert body["llm"] == {"name": "mock", "model": "mock-scripted-v1", "is_mock": True}
    assert body["embedding"]["dimensions"] == 768
    assert body["embedding"]["is_mock"] is True


def test_errors_are_problem_json(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 404
    assert body["instance"] == "/api/v1/does-not-exist"


def test_openapi_is_served(client):
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/health/ready" in r.json()["paths"]
