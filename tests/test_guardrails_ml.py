from chatbot_parking import guardrails


def test_contains_sensitive_data_uses_ml_pipeline(monkeypatch) -> None:
    def fake_ner(_: str):
        return [{"entity_group": "PERSON", "word": "John Doe"}]

    guardrails._load_ner_pipeline.cache_clear()
    monkeypatch.setattr(guardrails, "_load_ner_pipeline", lambda: fake_ner)

    assert guardrails.contains_sensitive_data("John Doe asked for access.") is True


def test_redact_sensitive_returns_redacted_when_ml_detects_sensitive(monkeypatch) -> None:
    def fake_ner(_: str):
        return [{"entity_group": "PERSON", "word": "Alice"}]

    guardrails._load_ner_pipeline.cache_clear()
    monkeypatch.setattr(guardrails, "_load_ner_pipeline", lambda: fake_ner)

    assert guardrails.redact_sensitive("Alice reservation details") == "[REDACTED]"
