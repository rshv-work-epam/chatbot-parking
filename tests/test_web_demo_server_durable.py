from fastapi.testclient import TestClient

from chatbot_parking import web_demo_server


client = TestClient(web_demo_server.app)


def test_chat_message_uses_durable_when_configured(monkeypatch):
    monkeypatch.setenv("DURABLE_BASE_URL", "https://func.example")

    def fake_invoke(message: str, thread_id: str):
        assert message == "hello"
        assert thread_id == "thread-123"
        return {
            "response": "hi from durable",
            "thread_id": thread_id,
            "mode": "info",
            "status": "collecting",
        }

    monkeypatch.setattr(web_demo_server, "_invoke_durable_chat", fake_invoke)

    response = client.post(
        "/chat/message",
        json={"message": "hello", "thread_id": "thread-123"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "hi from durable"


def test_admin_requests_require_token_when_configured(monkeypatch):
    monkeypatch.setenv("ADMIN_UI_TOKEN", "secret")

    unauthorized = client.get("/admin/requests")
    assert unauthorized.status_code == 401

    authorized = client.get("/admin/requests", headers={"x-api-token": "secret"})
    assert authorized.status_code == 200
    assert isinstance(authorized.json(), list)
