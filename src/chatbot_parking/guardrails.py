"""Guard rails to prevent sensitive data exposure."""

import re
from typing import Iterable

SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{16}\b"),  # credit card like sequences
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"password", re.IGNORECASE),
]


def contains_sensitive_data(text: str) -> bool:
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def filter_sensitive(chunks: Iterable[str]) -> list[str]:
    return [chunk for chunk in chunks if not contains_sensitive_data(chunk)]
