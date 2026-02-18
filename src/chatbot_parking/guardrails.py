"""Guardrails for LLM apps.

This module focuses on:
- Sensitive data detection/redaction (PII + common secrets/tokens)
- Basic prompt-injection / prompt-leakage pattern detection for untrusted text

These are intentionally lightweight heuristics, meant as a defense-in-depth layer
in addition to strict prompting, input validation, and least-privilege tool use.
"""

import os
import re
from typing import Iterable
from functools import lru_cache

SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{16}\b"),  # credit card like sequences
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"\b[A-Z]{2}\d{6,8}\b"),  # passport-like
    re.compile(r"\b\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3}[\s-]?\d{3,4}\b"),
    re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b"),
    re.compile(r"password", re.IGNORECASE),
    # Common secrets/tokens (best-effort; may be incomplete by design).
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),  # OpenAI (supports new sk-proj-* keys)
    re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),  # Google API key
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),  # GitHub token
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),  # Slack token
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\\.[a-zA-Z0-9_-]{10,}\\.[a-zA-Z0-9_-]{10,}\b"),  # JWT
]

PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bignore\b.*\b(previous|prior|above)\b.*\b(instructions|messages|context)\b", re.IGNORECASE),
    re.compile(r"\bdisregard\b.*\b(previous|prior|above)\b", re.IGNORECASE),
    re.compile(r"\bsystem prompt\b", re.IGNORECASE),
    re.compile(r"\bdeveloper message\b", re.IGNORECASE),
    re.compile(r"\breveal\b.*\b(system|developer)\b.*\b(prompt|message|instructions)\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bdo anything now\b", re.IGNORECASE),
    re.compile(r"\bprompt injection\b", re.IGNORECASE),
    re.compile(r"\bfunction call\b|\btool call\b|\bcall_tool\b", re.IGNORECASE),
]

SYSTEM_PROMPT_REQUEST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(system|developer)\s+(prompt|message|instructions)\b", re.IGNORECASE),
    re.compile(r"\bshow\b.*\b(system|developer)\b.*\b(prompt|message|instructions)\b", re.IGNORECASE),
    re.compile(r"\bwhat\b.*\b(system|developer)\b.*\b(prompt|message|instructions)\b", re.IGNORECASE),
]


def contains_prompt_injection(text: str) -> bool:
    sample = (text or "")[:4000]
    return any(pattern.search(sample) for pattern in PROMPT_INJECTION_PATTERNS)


def is_system_prompt_request(text: str) -> bool:
    sample = (text or "")[:2000]
    return any(pattern.search(sample) for pattern in SYSTEM_PROMPT_REQUEST_PATTERNS)


@lru_cache(maxsize=1)
def _load_ner_pipeline():
    app_env = os.getenv("APP_ENV", "dev").strip().lower() or "dev"
    default_enabled = "false" if app_env == "prod" else "true"
    if os.getenv("GUARDRAILS_USE_ML", default_enabled).lower() != "true":
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


def filter_prompt_injection(chunks: Iterable[str]) -> list[str]:
    return [chunk for chunk in chunks if not contains_prompt_injection(chunk)]


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
    max_chars = int(os.getenv("MAX_RESPONSE_CHARS", "4000"))
    if max_chars > 0 and len(text) > max_chars:
        trimmed = text[:max_chars].rstrip()
        return trimmed + ("..." if trimmed else "")
    return text
