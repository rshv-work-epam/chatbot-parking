from fastapi.testclient import TestClient

from chatbot_parking import web_demo_server


client = TestClient(web_demo_server.app)


def test_chat_message_uses_durable_when_configured(monkeypatch):
    monkeypatch.setenv("DURABLE_BASE_URL", "https://func.example")
    message = "I want to reserve a spot"

    def fake_invoke(message: str, thread_id: str):
        assert message == "I want to reserve a spot"
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
        json={"message": message, "thread_id": "thread-123"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "hi from durable"


def test_durable_status_poll_does_not_send_function_key_header(monkeypatch):
    monkeypatch.setenv("DURABLE_BASE_URL", "https://func.example")
    monkeypatch.setenv("DURABLE_FUNCTION_KEY", "func-key")

    def fake_post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
        assert url == "https://func.example/api/chat/start"
        assert (headers or {}).get("x-functions-key") == "func-key"
        return {
            "statusQueryGetUri": (
                "https://func.example/runtime/webhooks/durabletask/instances/abc?code=XYZ"
            )
        }

    seen_headers: list[dict] = []

    def fake_get_json(url: str, headers: dict | None = None) -> dict:
        # Durable webhook URIs include a `code` query param. We should not send x-functions-key,
        # otherwise the runtime may respond 403.
        seen_headers.append(dict(headers or {}))
        assert "x-functions-key" not in (headers or {})
        return {
            "runtimeStatus": "Completed",
            "output": {"response": "ok", "mode": "booking", "status": "collecting"},
        }

    monkeypatch.setattr(web_demo_server, "_post_json", fake_post_json)
    monkeypatch.setattr(web_demo_server, "_get_json", fake_get_json)

    result = web_demo_server._invoke_durable_chat("hello", "thread-123")
    assert result["response"] == "ok"
    assert seen_headers == [{}]


def test_admin_requests_require_token_when_configured(monkeypatch):
    monkeypatch.setenv("ADMIN_UI_TOKEN", "secret")

    unauthorized = client.get("/admin/requests")
    assert unauthorized.status_code == 401

    authorized = client.get("/admin/requests", headers={"x-api-token": "secret"})
    assert authorized.status_code == 200
    assert isinstance(authorized.json(), list)
