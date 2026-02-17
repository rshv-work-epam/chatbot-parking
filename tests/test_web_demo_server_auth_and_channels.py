from fastapi.testclient import TestClient

from chatbot_parking import web_demo_server
from chatbot_parking.persistence import InMemoryPersistence


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
