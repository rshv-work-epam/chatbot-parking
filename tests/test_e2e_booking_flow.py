import pytest
from fastapi.testclient import TestClient

from chatbot_parking import persistence as persistence_module
from chatbot_parking import web_demo_server


@pytest.fixture(autouse=True)
def _reset_in_memory_state(monkeypatch):
    # Ensure the e2e test runs locally (no Durable Functions / Cosmos).
    monkeypatch.delenv("DURABLE_BASE_URL", raising=False)
    monkeypatch.delenv("DURABLE_FUNCTION_KEY", raising=False)
    monkeypatch.setenv("MCP_RECORD_RESERVATIONS", "false")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "memory")
    monkeypatch.setenv("ADMIN_UI_TOKEN", "secret-token")

    persistence_module.get_persistence.cache_clear()
    persistence_module.IN_MEMORY_PERSISTENCE.threads.clear()
    persistence_module.IN_MEMORY_PERSISTENCE.approvals.clear()
    persistence_module.IN_MEMORY_PERSISTENCE.reservations.clear()
    yield
    persistence_module.get_persistence.cache_clear()
    persistence_module.IN_MEMORY_PERSISTENCE.threads.clear()
    persistence_module.IN_MEMORY_PERSISTENCE.approvals.clear()
    persistence_module.IN_MEMORY_PERSISTENCE.reservations.clear()


def test_end_to_end_booking_approval_flow():
    client = TestClient(web_demo_server.app)
    thread_id = "thread-e2e"

    # 1) Start booking
    resp = client.post("/chat/message", json={"message": "I want to reserve a spot", "thread_id": thread_id})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["mode"] == "booking"
    assert payload["status"] == "collecting"
    assert payload["pending_field"] == "name"

    # 2) Fill details (slot filling + validation)
    resp = client.post("/chat/message", json={"message": "John", "thread_id": thread_id})
    assert resp.json()["pending_field"] == "surname"

    resp = client.post("/chat/message", json={"message": "Doe", "thread_id": thread_id})
    assert resp.json()["pending_field"] == "car_number"

    resp = client.post("/chat/message", json={"message": "AA-1234", "thread_id": thread_id})
    assert resp.json()["pending_field"] == "reservation_period"

    resp = client.post(
        "/chat/message",
        json={"message": "2026-02-20 09:00 to 2026-02-20 10:00", "thread_id": thread_id},
    )
    payload = resp.json()
    assert payload["status"] == "review"
    assert payload["action_required"] == "review_confirmation"

    # 3) Submit for admin approval
    resp = client.post("/chat/message", json={"message": "confirm", "thread_id": thread_id})
    payload = resp.json()
    assert payload["status"] == "pending"
    request_id = payload.get("request_id")
    assert isinstance(request_id, str) and request_id

    # 4) Admin sees pending request and approves
    pending = client.get("/admin/requests", headers={"x-api-token": "secret-token"})
    assert pending.status_code == 200
    assert any(item.get("request_id") == request_id for item in pending.json())

    decision = client.post(
        "/admin/decision",
        headers={"x-api-token": "secret-token"},
        json={"request_id": request_id, "approved": True, "notes": "ok"},
    )
    assert decision.status_code == 200
    assert decision.json()["approved"] is True

    # 5) User checks status and reservation is recorded
    resp = client.post("/chat/message", json={"message": "status", "thread_id": thread_id})
    payload = resp.json()
    assert payload["status"] == "approved"
    assert "Confirmed" in payload["response"]

    assert len(persistence_module.IN_MEMORY_PERSISTENCE.reservations) == 1
    reservation = persistence_module.IN_MEMORY_PERSISTENCE.reservations[0]
    assert reservation.get("request_id") == request_id
    assert reservation.get("car_number") == "AA-1234"
