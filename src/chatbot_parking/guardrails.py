"""Guard rails to prevent sensitive data exposure."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{16}\b"),  # credit card like sequences
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"password", re.IGNORECASE),
]


@dataclass
class GuardrailConfig:
    model_name: str = "dslim/bert-base-NER"
    confidence_threshold: float = 0.6


class SensitiveDataDetector:
    def __init__(self, config: Optional[GuardrailConfig] = None) -> None:
        self.config = config or GuardrailConfig()
        self._pipeline = self._load_pipeline()

    def _load_pipeline(self):
        try:
            from transformers import pipeline
        except ImportError:
            return None
        try:
            return pipeline("token-classification", model=self.config.model_name, aggregation_strategy="simple")
        except Exception:
            return None

    def contains_sensitive_data(self, text: str) -> bool:
        if any(pattern.search(text) for pattern in SENSITIVE_PATTERNS):
            return True
        if not self._pipeline:
            return False
        try:
            entities = self._pipeline(text)
        except Exception:
            return False
        return any(entity.get("score", 0) >= self.config.confidence_threshold for entity in entities)


def filter_sensitive(chunks: Iterable[str], detector: Optional[SensitiveDataDetector] = None) -> list[str]:
    active_detector = detector or SensitiveDataDetector()
    return [chunk for chunk in chunks if not active_detector.contains_sensitive_data(chunk)]
