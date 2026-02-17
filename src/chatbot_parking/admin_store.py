"""Shared admin approval store built on pluggable persistence."""

from __future__ import annotations

from typing import Any

from chatbot_parking.persistence import IN_MEMORY_PERSISTENCE, get_persistence

# Backward compatibility alias for tests that inspect in-memory state.
STORE = IN_MEMORY_PERSISTENCE.approvals


def create_admin_request(payload: dict[str, Any]) -> str:
    return get_persistence().create_approval(payload)


def list_pending_requests() -> list[dict[str, Any]]:
    return get_persistence().list_pending_approvals()


def get_admin_request(request_id: str) -> dict[str, Any] | None:
    return get_persistence().get_approval(request_id)


def get_admin_decision(request_id: str) -> dict[str, Any] | None:
    request = get_persistence().get_approval(request_id)
    if not request:
        return None
    return request.get("decision")


def post_admin_decision(request_id: str, approved: bool, notes: str | None = None) -> dict[str, Any] | None:
    return get_persistence().set_approval_decision(
        request_id=request_id,
        approved=approved,
        notes=notes,
    )
