"""Static knowledge base for the parking chatbot."""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(r"C:\Users\RomanShevchuk\Downloads\chatbot-parking-main_test\data\static_docs.json")


def load_static_documents() -> list[dict]:
    if not DATA_PATH.exists():
        raise FileNotFoundError("Static documents not found at data/static_docs.json")
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


STATIC_DOCUMENTS = load_static_documents()
