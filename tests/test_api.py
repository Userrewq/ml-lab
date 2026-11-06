import json
import asyncio
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src import api


TOKEN = "test-lab4-token"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)

    # Reset the global limiter between tests.
    original_limiter = api.rate_limiter
    api.rate_limiter.requests.clear()

    try:
        with TestClient(api.app) as test_client:
            yield test_client
    finally:
        api.rate_limiter = original_limiter


@pytest.fixture
def valid_payload():
    df = pd.read_csv(api.ROOT / "data/ci/control_X.csv", nrows=1)
    return {"rows": df.to_dict(orient="records")}


def auth_headers():
    return {"X-API-Token": TOKEN}


def test_health_healthy(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_index_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "DNS Tunneling Detection" in response.text


def test_predict_valid(client, valid_payload):
    response = client.post(
        "/predict",
        headers=auth_headers(),
        json=valid_payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["prediction"]) == 1
    assert body["model_version"]
    assert body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_predict_without_token(client):
    response = client.post("/predict", json={"rows": []})

    assert response.status_code == 401


def test_predict_wrong_token(client):
    response = client.post(
        "/predict",
        headers={"X-API-Token": "wrong-token"},
        json={"rows": []},
    )

    assert response.status_code == 401


def test_predict_empty_rows(client):
    response = client.post(
        "/predict",
        headers=auth_headers(),
        json={"rows": []},
    )

    assert response.status_code == 422


def test_predict_wrong_schema(client):
    response = client.post(
        "/predict",
        headers=auth_headers(),
        json={"data": [1, 2, 3]},
    )

    assert response.status_code == 422


def test_predict_wrong_feature_type(client, valid_payload):
    valid_payload["rows"][0]["src_port"] = "not-a-number"

    response = client.post(
        "/predict",
        headers=auth_headers(),
        json=valid_payload,
    )

    assert response.status_code == 422


def test_predict_nan_rejected(client, valid_payload):
    valid_payload["rows"][0]["src_port"] = float("nan")

    response = client.post(
        "/predict",
        headers={
            **auth_headers(),
            "Content-Type": "application/json",
        },
        content=json.dumps(valid_payload, allow_nan=True),
    )

    assert response.status_code == 422

def test_predict_wrong_content_type(client):
    response = client.post(
        "/predict",
        headers={
            **auth_headers(),
            "Content-Type": "text/plain",
        },
        content='{"rows":[]}',
    )

    assert response.status_code == 415


def test_predict_oversized_body(client):
    response = client.post(
        "/predict",
        headers={
            **auth_headers(),
            "Content-Type": "application/json",
        },
        content=b"x" * (api.MAX_BODY_BYTES + 1),
    )

    assert response.status_code == 413


def test_predict_rate_limit(client, valid_payload):
    api.rate_limiter = api.InMemoryRateLimiter(
        limit=2,
        window_seconds=60,
    )

    first = client.post(
        "/predict",
        headers=auth_headers(),
        json=valid_payload,
    )
    second = client.post(
        "/predict",
        headers=auth_headers(),
        json=valid_payload,
    )
    third = client.post(
        "/predict",
        headers=auth_headers(),
        json=valid_payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_rejected_input_does_not_call_predict(client, monkeypatch):
    class PredictorSpy:
        def __init__(self):
            self.called = False

        def predict(self, frame):
            self.called = True
            raise AssertionError("Predict must not be called")

    spy = PredictorSpy()
    api.state["predictor"] = spy

    response = client.post(
        "/predict",
        headers=auth_headers(),
        json={"rows": []},
    )

    assert response.status_code == 422
    assert spy.called is False


def test_health_not_ready_on_hash_mismatch(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)

    def reject_model(*args, **kwargs):
        raise ValueError("hash mismatch")

    monkeypatch.setattr(api, "verify_model_integrity", reject_model)

    with TestClient(api.app) as test_client:
        response = test_client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"

def test_body_limit_without_content_length():
    from src.api_protection import BodyLimitMiddleware

    app_called = False
    sent_messages = []
    chunks = [
        {
            "type": "http.request",
            "body": b"x" * 8,
            "more_body": True,
        },
        {
            "type": "http.request",
            "body": b"x" * 8,
            "more_body": False,
        },
    ]

    async def fake_app(scope, receive, send):
        nonlocal app_called
        app_called = True

    async def receive():
        return chunks.pop(0)

    async def send(message):
        sent_messages.append(message)

    middleware = BodyLimitMiddleware(fake_app, max_bytes=10)

    asyncio.run(
        middleware(
            {
                "type": "http",
                "path": "/predict",
                "headers": [],
                "method": "POST",
            },
            receive,
            send,
        )
    )

    assert app_called is False
    assert sent_messages[0]["status"] == 413

def test_metrics_requires_token(client):
    response = client.get("/metrics")

    assert response.status_code == 401


def test_metrics_with_token(client):
    response = client.get(
        "/metrics",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert "dns_api_requests_total" in response.text
    assert "dns_api_request_duration_seconds" in response.text

