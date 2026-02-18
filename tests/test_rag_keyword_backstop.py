import chatbot_parking.chatbot as chatbot_module
from chatbot_parking.chatbot import ParkingChatbot

from langchain_core.documents import Document


def test_keyword_backstop_adds_rules_context(monkeypatch):
    bot = ParkingChatbot()

    class DummyStore:
        def similarity_search(self, _query: str, k: int = 3):
            return [
                Document(
                    page_content="irrelevant context",
                    metadata={"id": "parking_overview", "sensitivity": "public"},
                )
            ]

    bot.vector_store = DummyStore()

    seen: dict[str, str] = {}

    def fake_generate_answer(question: str, context: str, dynamic_info: str) -> str:
        seen["question"] = question
        seen["context"] = context
        seen["dynamic"] = dynamic_info
        return "ok"

    monkeypatch.setattr(chatbot_module, "generate_answer", fake_generate_answer)

    result = bot.answer_question("rules")
    assert result == "ok"
    assert "rules" in seen["question"].lower()
    assert "arrive within 30 minutes" in seen["context"].lower()

