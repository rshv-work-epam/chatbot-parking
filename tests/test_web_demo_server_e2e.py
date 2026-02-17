from fastapi.testclient import TestClient

from chatbot_parking import admin_store, web_demo_server
from chatbot_parking.persistence import InMemoryPersistence


def test_e2e_booking_admin_approve_records_reservation(monkeypatch):
    persistence = InMemoryPersistence()
    monkeypatch.setattr(web_demo_server, "get_persistence", lambda: persistence)
    monkeypatch.setattr(admin_store, "get_persistence", lambda: persistence)
    monkeypatch.setenv("ADMIN_UI_TOKEN", "secret")
    monkeypatch.delenv("DURABLE_BASE_URL", raising=False)

    client = TestClient(web_demo_server.app)

    start = client.post("/chat/message", json={"message": "I want to reserve a spot"})
    assert start.status_code == 200
    thread_id = start.json()["thread_id"]

    client.post("/chat/message", json={"thread_id": thread_id, "message": "Roman"})
    client.post("/chat/message", json={"thread_id": thread_id, "message": "Shevchuk"})
    client.post("/chat/message", json={"thread_id": thread_id, "message": "AA-1234-BB"})
    pending = client.post(
        "/chat/message",
        json={"thread_id": thread_id, "message": "2026-02-20 09:00 to 2026-02-20 18:00"},
    )
    assert pending.status_code == 200
    request_id = pending.json()["request_id"]

    listed = client.get("/admin/requests", headers={"x-api-token": "secret"})
    assert listed.status_code == 200
    assert any(item["request_id"] == request_id for item in listed.json())

    decided = client.post(
        "/admin/decision",
        json={"request_id": request_id, "approved": True, "notes": "ok"},
        headers={"x-api-token": "secret"},
    )
    assert decided.status_code == 200
    assert decided.json()["approved"] is True

    confirmed = client.post("/chat/message", json={"thread_id": thread_id, "message": "status?"})
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "approved"
    assert persistence.reservations
