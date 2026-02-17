from fastapi.testclient import TestClient

from chatbot_parking import web_demo_server
from chatbot_parking.http_security import reset_rate_limiter


def test_security_headers_are_set():
    client = TestClient(web_demo_server.app)
    resp = client.get("/chat/ui")

    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in resp.headers


def test_rate_limit_blocks_excess_requests(monkeypatch):
    client = TestClient(web_demo_server.app)

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    reset_rate_limiter(max_requests=1, window_seconds=60)

    monkeypatch.setattr(
        web_demo_server,
        "_run_chat_turn",
        lambda thread_id, message: {
            "response": "ok",
            "thread_id": thread_id,
            "mode": "info",
            "status": "collecting",
        },
    )

    first = client.post("/chat/message", json={"message": "hello", "thread_id": "t1"})
    assert first.status_code == 200

    second = client.post("/chat/message", json={"message": "hello again", "thread_id": "t1"})
    assert second.status_code == 429
