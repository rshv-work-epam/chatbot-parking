from fastapi.testclient import TestClient

from chatbot_parking import web_demo_server
from chatbot_parking.persistence import InMemoryPersistence
import hashlib
import hmac
import json as jsonlib


client = TestClient(web_demo_server.app)


def test_auth_endpoints_guest_mode() -> None:
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] in {True, False}

    providers = client.get("/auth/providers")
    assert providers.status_code == 200
    assert isinstance(providers.json().get("providers"), list)


def test_chat_message_returns_fallback_on_llm_error(monkeypatch) -> None:
    persistence = InMemoryPersistence()
    monkeypatch.setattr(web_demo_server, "get_persistence", lambda: persistence)
    monkeypatch.delenv("DURABLE_BASE_URL", raising=False)

    def _raise(_: str) -> str:
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(web_demo_server.chatbot, "answer_question", _raise)

    response = client.post("/chat/message", json={"message": "some random info question"})

    assert response.status_code == 200
    assert "unavailable" in response.json()["response"].lower()


def test_openai_tool_channel_adapter() -> None:
    response = client.post(
        "/channels/openai/tool",
        json={"input": "reserve spot", "user_id": "user-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"].startswith("openai:user-1")
    assert isinstance(body["output"], str)


def test_generic_channel_adapter() -> None:
    response = client.post(
        "/channels/generic/message",
        json={"channel": "webchat", "user_id": "u1", "message": "reserve a place"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == "webchat:u1"
    assert body["channel"] == "webchat"


def test_message_length_limits(monkeypatch) -> None:
    monkeypatch.setenv("MAX_MESSAGE_CHARS", "5")

    response = client.post("/chat/message", json={"message": "123456"})
    assert response.status_code == 413


def test_thread_id_length_limits(monkeypatch) -> None:
    monkeypatch.setenv("MAX_THREAD_ID_CHARS", "5")

    response = client.post("/chat/message", json={"message": "hi", "thread_id": "123456"})
    assert response.status_code == 413


def test_version_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("BUILD_SHA", "abc123")
    monkeypatch.setenv("BUILD_TIME", "2026-02-18T00:00:00Z")
    monkeypatch.setenv("APP_ENV", "prod")

    resp = client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["git_sha"] == "abc123"
    assert data["build_time"] == "2026-02-18T00:00:00Z"
    assert data["app_env"] == "prod"


def test_docs_disabled_in_prod(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")

    resp = client.get("/docs")
    assert resp.status_code == 404


def test_whatsapp_webhook_signature_required_when_secret_set(monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")

    payload = {"entry": []}
    body = jsonlib.dumps(payload).encode("utf-8")

    invalid = client.post(
        "/channels/whatsapp/webhook",
        data=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": "sha256=deadbeef",
        },
    )
    assert invalid.status_code == 401

    digest = hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    valid = client.post(
        "/channels/whatsapp/webhook",
        data=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": f"sha256={digest}",
        },
    )
    assert valid.status_code == 200
