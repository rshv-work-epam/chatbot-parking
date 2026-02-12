"""Static knowledge base for the parking chatbot."""

from __future__ import annotations

import json
import os
from pathlib import Path

def _find_data_path() -> Path:
    """Find the data directory, trying multiple possible locations."""
    possible_paths = [
        Path(__file__).parent.parent.parent / "data" / "static_docs.json",
        Path("/workspaces/chatbot-parking/data/static_docs.json"),
        Path("./data/static_docs.json"),
        Path("../data/static_docs.json"),
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
