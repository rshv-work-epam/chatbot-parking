"""Guard rails to prevent sensitive data exposure."""

from functools import lru_cache
import os
import re
from typing import Iterable

SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{16}\b"),  # credit card like sequences
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"\b[A-Z]{2}\d{6,8}\b"),  # passport-like
    re.compile(r"\b\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3}[\s-]?\d{3,4}\b"),
    re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b"),
    re.compile(r"password", re.IGNORECASE),
]


@lru_cache(maxsize=1)
def _load_ner_pipeline():
    if os.getenv("GUARDRAILS_USE_ML", "false").lower() != "true":
        return None
    try:
        from transformers import pipeline

        model_name = os.getenv("GUARDRAILS_NER_MODEL", "dslim/bert-base-NER")
        return pipeline(
            "token-classification",
            model=model_name,
            aggregation_strategy="simple",
        )
    except Exception:
        return None


def _contains_sensitive_via_ml(text: str) -> bool:
    ner = _load_ner_pipeline()
    if ner is None:
        return False
    try:
        entities = ner(text[:1000])
    except Exception:
        return False

    sensitive_groups = {"PER", "PERSON", "EMAIL", "PHONE"}
    return any(entity.get("entity_group") in sensitive_groups for entity in entities)


def contains_sensitive_data(text: str) -> bool:
    if any(pattern.search(text) for pattern in SENSITIVE_PATTERNS):
        return True
    return _contains_sensitive_via_ml(text)


def filter_sensitive(chunks: Iterable[str]) -> list[str]:
    return [chunk for chunk in chunks if not contains_sensitive_data(chunk)]


def redact_sensitive(text: str) -> str:
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    if _contains_sensitive_via_ml(redacted):
        return "[REDACTED]"
    return redacted


def safe_output(text: str) -> str:
    if contains_sensitive_data(text):
        return "Sorry, I cannot share private information."
    return text
