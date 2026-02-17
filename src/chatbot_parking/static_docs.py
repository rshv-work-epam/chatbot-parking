"""Static knowledge base for the parking chatbot."""

from __future__ import annotations

import json
import os
from pathlib import Path

def _find_data_path() -> Path:
    """Resolve static documents path from env or known repository locations."""
    explicit = os.getenv("STATIC_DOCS_PATH")
    if explicit:
        path = Path(explicit)
        if path.exists():
            return path

    possible_paths = [
        Path(__file__).resolve().parents[2] / "data" / "static_docs.json",
        Path.cwd() / "data" / "static_docs.json",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    raise FileNotFoundError(f"Static documents not found. Tried: {[str(p) for p in possible_paths]}")

DATA_PATH = _find_data_path()

def load_static_documents() -> list[dict]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Static documents not found at {DATA_PATH}")
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


STATIC_DOCUMENTS = load_static_documents()
