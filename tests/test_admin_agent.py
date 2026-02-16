from chatbot_parking.admin_agent import request_admin_approval
from chatbot_parking.chatbot import ReservationRequest


def test_request_admin_approval_uses_http_when_admin_api_url_set(monkeypatch):
    monkeypatch.setenv("ADMIN_API_URL", "http://admin-ui.local")
    monkeypatch.setenv("ADMIN_AUTO_APPROVE", "true")

    calls = []

    def fake_post_json(url, payload):
        calls.append((url, payload))
        if url.endswith("/admin/request"):
            return {"request_id": "req-123"}
        if url.endswith("/admin/decision"):
            return {
                "approved": True,
                "decided_at": "2025-01-01T00:00:00Z",
                "notes": "ok",
            }
        raise AssertionError(f"Unexpected URL called: {url}")

    monkeypatch.setattr("chatbot_parking.admin_agent._post_json", fake_post_json)

    decision = request_admin_approval(
        ReservationRequest(
            name="Alex",
            surname="Morgan",
            car_number="XY-1234",
            reservation_period="2026-02-20 09:00 to 2026-02-20 18:00",
        )
    )

    assert decision.approved is True
    assert calls[0][0] == "http://admin-ui.local/admin/request"
