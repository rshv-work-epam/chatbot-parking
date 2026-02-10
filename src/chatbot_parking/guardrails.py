"""Guard rails to prevent sensitive data exposure."""

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


def contains_sensitive_data(text: str) -> bool:
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def filter_sensitive(chunks: Iterable[str]) -> list[str]:
    return [chunk for chunk in chunks if not contains_sensitive_data(chunk)]


def redact_sensitive(text: str) -> str:
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def safe_output(text: str) -> str:
    if contains_sensitive_data(text):
        return "Sorry, I cannot share private information."
    return text
