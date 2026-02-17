"""Durable activity: runs one booking chat turn using shared persistence."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from func_bootstrap import ensure_src_on_path

ensure_src_on_path()

from chatbot_parking.interactive_flow import run_chat_turn
from chatbot_parking.persistence import get_persistence


def _durable_answer_question(_text: str) -> str:
    # Durable is used for booking/approval orchestration. Keep Functions deps minimal.
    return "Info questions are handled by the UI service. Start a booking to continue."


def main(payload: dict[str, Any]) -> dict[str, Any]:
    message = str(payload.get("message", "")).strip()
    thread_id = str(payload.get("thread_id", "")).strip() or str(uuid4())

    if not message:
        return {
            "response": "Message cannot be empty",
            "thread_id": thread_id,
            "mode": "info",
            "status": "collecting",
        }

    persistence = get_persistence()
    prior_state = persistence.get_thread(thread_id)
    result, next_state = run_chat_turn(
        message=message,
        state=prior_state,
        persistence=persistence,
        answer_question=_durable_answer_question,
    )
    persistence.upsert_thread(thread_id, next_state)

    response = {
        **result,
        "thread_id": thread_id,
    }
    response.setdefault("response", "")
    response.setdefault("mode", "info")
    response.setdefault("status", "collecting")
    return response

