"""Shared interactive chat turn logic for UI and Durable backend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from chatbot_parking.booking_utils import (
    BOOKING_FIELDS,
    apply_valid_parsed_details,
    is_booking_keyword_intent,
    next_missing_field,
    normalize_car_number,
    normalize_reservation_period,
    parse_structured_details,
    validate_field,
)
from chatbot_parking.persistence import Persistence

FIELD_PROMPTS: dict[str, str] = {
    "name": "Please provide your name.",
    "surname": "Please provide your surname.",
    "car_number": "What is your car number?",
    "reservation_period": "What reservation period would you like (e.g., 2026-02-20 09:00 to 2026-02-20 18:00)?",
}


def _next_field(current: str | None) -> str | None:
    if current is None or current not in BOOKING_FIELDS:
        return None
    idx = BOOKING_FIELDS.index(current)
    return BOOKING_FIELDS[idx + 1] if idx + 1 < len(BOOKING_FIELDS) else None


def default_state() -> dict[str, Any]:
    return {
        "mode": "info",
        "booking_active": False,
        "pending_field": None,
        "collected": {},
        "request_id": None,
        "status": "collecting",
        "recorded": False,
    }


def _state_with(base: dict[str, Any], **updates: Any) -> dict[str, Any]:
    merged = dict(base)
    merged.update(updates)
    return merged


def run_chat_turn(
    *,
    message: str,
    state: dict[str, Any] | None,
    persistence: Persistence,
    answer_question,
) -> tuple[dict[str, Any], dict[str, Any]]:
    text = message.strip()
    if not text:
        current = state or default_state()
        return (
            {
                "response": "Message cannot be empty.",
                "mode": current.get("mode", "info"),
            },
            current,
        )

    current = _state_with(default_state(), **(state or {}))
    booking_active = bool(current.get("booking_active", False))
    pending_field = current.get("pending_field")
    collected = dict(current.get("collected") or {})
    status = current.get("status")
    request_id = current.get("request_id")
    recorded = bool(current.get("recorded", False))

    if is_booking_keyword_intent(text):
        next_state = _state_with(
            current,
            mode="booking",
            booking_active=True,
            pending_field="name",
            collected={},
            status="collecting",
            request_id=None,
            recorded=False,
        )
        return ({"response": FIELD_PROMPTS["name"], "mode": "booking"}, next_state)

    if booking_active and status == "pending" and request_id:
        approval = persistence.get_approval(request_id)
        decision = approval.get("decision") if approval else None

        if decision and decision.get("approved") is True:
            if not recorded:
                approval_time = decision.get("decided_at") or datetime.now(timezone.utc).isoformat()
                persistence.append_reservation(
                    name=f"{collected.get('name', '').strip()} {collected.get('surname', '').strip()}".strip(),
                    car_number=collected.get("car_number", ""),
                    reservation_period=collected.get("reservation_period", ""),
                    approval_time=approval_time,
                    request_id=request_id,
                )
            next_state = _state_with(
                current,
                response="Confirmed and recorded.",
                mode="booking",
                booking_active=False,
                pending_field=None,
                status="approved",
                recorded=True,
            )
            return (
                {
                    "response": "Confirmed and recorded.",
                    "mode": "booking",
                    "request_id": request_id,
                    "status": "approved",
                },
                next_state,
            )

        if decision and decision.get("approved") is False:
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=False,
                pending_field=None,
                status="declined",
                recorded=False,
            )
            return (
                {
                    "response": "Declined by administrator.",
                    "mode": "booking",
                    "request_id": request_id,
                    "status": "declined",
                },
                next_state,
            )

        next_state = _state_with(current, mode="booking", booking_active=True, pending_field=None, status="pending")
        return (
            {
                "response": f"Still pending administrator decision. Request id: {request_id}",
                "mode": "booking",
                "request_id": request_id,
                "status": "pending",
            },
            next_state,
        )

    if booking_active and pending_field:
        parsed = parse_structured_details(text)
        if parsed:
            collected = apply_valid_parsed_details(collected, parsed)
            pending_field = next_missing_field(collected)
            if pending_field is None:
                new_request_id = persistence.create_approval(
                    {
                        "name": collected.get("name", ""),
                        "surname": collected.get("surname", ""),
                        "car_number": collected.get("car_number", ""),
                        "reservation_period": collected.get("reservation_period", ""),
                    }
                )
                next_state = _state_with(
                    current,
                    mode="booking",
                    booking_active=True,
                    pending_field=None,
                    collected=collected,
                    request_id=new_request_id,
                    status="pending",
                    recorded=False,
                )
                return (
                    {
                        "response": f"Submitted for approval. Request id: {new_request_id}",
                        "mode": "booking",
                        "request_id": new_request_id,
                        "status": "pending",
                    },
                    next_state,
                )
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=True,
                pending_field=pending_field,
                collected=collected,
                status="collecting",
            )
            return (
                {
                    "response": FIELD_PROMPTS[pending_field],
                    "mode": "booking",
                    "status": "collecting",
                },
                next_state,
            )

        error = validate_field(pending_field, text)
        if error:
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=True,
                pending_field=pending_field,
                collected=collected,
                status="collecting",
            )
            return (
                {
                    "response": f"Invalid {pending_field}: {error} {FIELD_PROMPTS[pending_field]}",
                    "mode": "booking",
                    "status": "collecting",
                },
                next_state,
            )

        if pending_field == "car_number":
            collected[pending_field] = normalize_car_number(text)
        elif pending_field == "reservation_period":
            collected[pending_field] = normalize_reservation_period(text)
        else:
            collected[pending_field] = text
        next_field = _next_field(pending_field)
        if next_field is not None:
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=True,
                pending_field=next_field,
                collected=collected,
                status="collecting",
            )
            return (
                {
                    "response": FIELD_PROMPTS[next_field],
                    "mode": "booking",
                    "status": "collecting",
                },
                next_state,
            )

        new_request_id = persistence.create_approval(
            {
                "name": collected.get("name", ""),
                "surname": collected.get("surname", ""),
                "car_number": collected.get("car_number", ""),
                "reservation_period": collected.get("reservation_period", ""),
            }
        )
        next_state = _state_with(
            current,
            mode="booking",
            booking_active=True,
            pending_field=None,
            collected=collected,
            request_id=new_request_id,
            status="pending",
            recorded=False,
        )
        return (
            {
                "response": f"Submitted for approval. Request id: {new_request_id}",
                "mode": "booking",
                "request_id": new_request_id,
                "status": "pending",
            },
            next_state,
        )

    response = answer_question(text)
    next_state = _state_with(
        current,
        mode="info",
        booking_active=False,
        pending_field=None,
        collected={},
        request_id=None,
        status="collecting",
        recorded=False,
    )
    return (
        {
            "response": response,
            "mode": "info",
            "status": "collecting",
        },
        next_state,
    )
