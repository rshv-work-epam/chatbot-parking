from fastapi.testclient import TestClient

from chatbot_parking import web_demo_server


client = TestClient(web_demo_server.app)


def test_chat_ask_returns_chatbot_response(monkeypatch):
    monkeypatch.setattr(web_demo_server.chatbot, "answer_question", lambda _: "Hours: 09:00-22:00")

    response = client.post("/chat/ask", json={"message": "What are the working hours?"})

    assert response.status_code == 200
    assert response.json()["response"] == "Hours: 09:00-22:00"


def test_chat_ui_is_served():
    response = client.get("/chat/ui")

    assert response.status_code == 200
    assert "Parking Chatbot" in response.text
