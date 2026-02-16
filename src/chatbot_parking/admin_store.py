"""Shared in-memory store for admin approval requests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

STORE: dict[str, dict[str, Any]] = {}


def create_admin_request(payload: dict[str, Any]) -> str:
    request_id = str(uuid4())
    STORE[request_id] = {
        "request_id": request_id,
        "payload": payload,
        "decision": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return request_id


def list_pending_requests() -> list[dict[str, Any]]:
    return [entry for entry in STORE.values() if not entry.get("decision")]


def get_admin_decision(request_id: str) -> dict[str, Any] | None:
    entry = STORE.get(request_id)
    if not entry:
        return None
    return entry.get("decision")


def post_admin_decision(request_id: str, approved: bool, notes: str | None = None) -> dict[str, Any] | None:
    entry = STORE.get(request_id)
    if not entry:
        return None

    decision = {
        "approved": approved,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    entry["decision"] = decision
    return decision
