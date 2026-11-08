"""The /metrics route follows proxy authentication and reflects finished requests."""

import pytest
from fastapi.testclient import TestClient

from free_claude_code.api.dependencies import get_settings
from free_claude_code.config.settings import Settings
from free_claude_code.core.metrics import REQUEST_METRICS
from tests.api.support import create_test_app


@pytest.fixture(autouse=True)
def clean_metrics():
    REQUEST_METRICS.reset()
    yield
    REQUEST_METRICS.reset()


@pytest.fixture
def app():
    return create_test_app(Settings())


def test_metrics_exposes_prometheus_text(app):
    REQUEST_METRICS.record(
        provider_id="nvidia_nim",
        model="m",
        wire_api="messages",
        outcome="success",
        duration_seconds=0.4,
    )
    response = TestClient(app).get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert response.headers["cache-control"] == "no-store"
    assert 'fcc_requests_total{provider="nvidia_nim"' in response.text


def test_metrics_requires_proxy_token_when_auth_is_enabled(app):
    client = TestClient(app)
    settings = Settings(proxy_auth_enabled=True, proxy_auth_token="s3cr3t")
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        assert client.get("/metrics").status_code == 401
        assert (
            client.get(
                "/metrics", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/metrics", headers={"Authorization": "Bearer s3cr3t"}
            ).status_code
            == 200
        )
    finally:
        app.dependency_overrides.clear()


def test_outcome_middleware_records_one_series_per_finished_request():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    from free_claude_code.api.request_outcomes import RequestOutcomeMiddleware
    from free_claude_code.core.request_outcomes import record_request_route

    async def messages(request):
        record_request_route("groq", "llama")
        return JSONResponse({"ok": True})

    async def health(request):
        return JSONResponse({"ok": True})

    app = Starlette(
        routes=[
            Route("/v1/messages", messages, methods=["POST"]),
            Route("/health", health),
        ],
        middleware=[],
    )
    app.add_middleware(RequestOutcomeMiddleware)
    client = TestClient(app)
    assert client.post("/v1/messages", json={}).status_code == 200
    assert client.get("/health").status_code == 200

    assert REQUEST_METRICS.snapshot().keys() == {
        ("groq", "llama", "messages", "success")
    }
