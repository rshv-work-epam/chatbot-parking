"""Shared interactive chat turn logic for UI and Durable backend."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from chatbot_parking.persistence import Persistence

BOOKING_FIELDS: list[str] = ["name", "surname", "car_number", "reservation_period"]
FIELD_PROMPTS: dict[str, str] = {
    "name": "Please provide your name.",
    "surname": "Please provide your surname.",
    "car_number": "What is your car number?",
    "reservation_period": "What reservation period would you like (e.g., 2026-02-20 09:00 to 2026-02-20 18:00)?",
}

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z' -]{1,49}$")
CAR_RE = re.compile(r"^[A-Z0-9-]{4,12}$")
PERIOD_RE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+to\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*$",
    re.IGNORECASE,
)


def _next_field(current: str | None) -> str | None:
    if current is None or current not in BOOKING_FIELDS:
        return None
    idx = BOOKING_FIELDS.index(current)
    return BOOKING_FIELDS[idx + 1] if idx + 1 < len(BOOKING_FIELDS) else None


def _is_booking_intent(message: str) -> bool:
    lowered = message.lower()
    keywords = ["book", "reserve", "reservation", "броню", "заброню"]
    return any(word in lowered for word in keywords)


def _validate_field(field: str, value: str) -> str | None:
    if field in {"name", "surname"}:
        if not NAME_RE.fullmatch(value):
            return "Use only letters, spaces, apostrophe, or hyphen (2-50 chars)."
        return None

    if field == "car_number":
        normalized = value.upper().replace(" ", "")
        if not CAR_RE.fullmatch(normalized):
            return "Car number must be 4-12 chars: letters, digits, or '-' only."
        return None

    if field == "reservation_period":
        match = PERIOD_RE.match(value)
        if not match:
            return "Use format: YYYY-MM-DD HH:MM to YYYY-MM-DD HH:MM."
        start = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")
        end = datetime.strptime(match.group(2), "%Y-%m-%d %H:%M")
        if end <= start:
            return "Reservation end time must be after start time."
        return None

    return None


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

    if _is_booking_intent(text):
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
        error = _validate_field(pending_field, text)
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
            collected[pending_field] = text.upper().replace(" ", "")
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
