import chatbot_parking.config as config
from chatbot_parking.rag import generate_answer


def _set_llm_provider(monkeypatch, provider: str) -> None:
    monkeypatch.setenv("LLM_PROVIDER", provider)
    config.get_settings.cache_clear()


def test_echo_provider_answers_dynamic_info(monkeypatch):
    _set_llm_provider(monkeypatch, "echo")
    dynamic = "Current availability: 5 spaces. Hours: 08:00-20:00. Pricing: $10/hour."
    response = generate_answer("What are your working hours?", context="", dynamic_info=dynamic)
    assert "I could not generate an answer." not in response
    assert "08:00-20:00" in response


def test_echo_provider_gibberish_returns_help(monkeypatch):
    _set_llm_provider(monkeypatch, "echo")
    dynamic = "Current availability: 5 spaces. Hours: 08:00-20:00. Pricing: $10/hour."
    response = generate_answer("zxcv", context="", dynamic_info=dynamic)
    assert "I could not generate an answer." not in response
    assert "Try asking" in response

