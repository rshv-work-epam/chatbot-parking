"""Ingest static documents into the vector store with guardrails."""

from __future__ import annotations

import json
from pathlib import Path

from chatbot_parking.guardrails import contains_sensitive_data, redact_sensitive
from chatbot_parking.guardrails import contains_prompt_injection
from chatbot_parking.rag import build_vector_store
from chatbot_parking.static_docs import load_static_documents

OUTPUT_PATH = Path("data/ingest_report.json")


def ingest() -> dict:
    documents = load_static_documents()
    redacted_count = 0
    injection_count = 0
    injection_ids: list[str] = []
    processed = []

    for doc in documents:
        redacted_text = redact_sensitive(doc["text"])
        if redacted_text != doc["text"]:
            redacted_count += 1
        if contains_prompt_injection(doc["text"]):
            injection_count += 1
            injection_ids.append(str(doc.get("id") or "unknown"))
        processed.append(
            {
                "id": doc["id"],
                "sensitivity": "private" if contains_sensitive_data(doc["text"]) else "public",
                "text": redacted_text,
            }
        )

    build_vector_store()
    report = {
        "total_documents": len(processed),
        "redacted_documents": redacted_count,
        "prompt_injection_documents": injection_count,
        "prompt_injection_ids": injection_ids[:20],
        "output_path": str(OUTPUT_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(ingest(), indent=2))
