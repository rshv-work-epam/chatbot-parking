"""Shared interactive chat turn logic for UI and Durable backend."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Callable

from chatbot_parking.booking_utils import (
    BOOKING_FIELDS,
    apply_valid_parsed_details,
    is_booking_keyword_intent,
    is_period_within_working_hours,
    next_missing_field,
    normalize_car_number,
    normalize_reservation_period,
    parse_structured_details,
    suggest_alternative_periods,
    validate_field,
)
from chatbot_parking.dynamic_data import get_dynamic_info
from chatbot_parking.persistence import Persistence

FIELD_PROMPTS: dict[str, str] = {
    "name": "Please provide your name.",
    "surname": "Please provide your surname.",
    "car_number": "What is your car number?",
    "reservation_period": "What reservation period would you like (e.g., 2026-02-20 09:00 to 2026-02-20 18:00)?",
}

CONFIRM_COMMANDS = {"confirm", "submit", "yes", "approve", "ok"}
CANCEL_COMMANDS = {"cancel", "stop", "abort", "quit"}
STATUS_LABELS: dict[str, str] = {
    "collecting": "Collecting booking details",
    "review": "Waiting for your confirmation",
    "pending": "Pending administrator review",
    "approved": "Approved",
    "declined": "Declined",
    "cancelled": "Cancelled",
}
FIELD_LABELS: dict[str, str] = {
    "name": "Name",
    "surname": "Surname",
    "car_number": "Car number",
    "reservation_period": "Reservation period",
}


def _next_field(current: str | None) -> str | None:
    if current is None or current not in BOOKING_FIELDS:
        return None
    idx = BOOKING_FIELDS.index(current)
    return BOOKING_FIELDS[idx + 1] if idx + 1 < len(BOOKING_FIELDS) else None


def _status_detail(status: str, collected: dict[str, Any]) -> str:
    if status == "collecting":
        done = sum(1 for field in BOOKING_FIELDS if str(collected.get(field, "")).strip())
        return f"Collecting details ({done}/{len(BOOKING_FIELDS)} complete)."
    if status == "review":
        return "Review details, then send 'confirm' to submit, or 'edit <field>'."
    if status == "pending":
        return "Request submitted. Waiting for administrator decision."
    if status == "approved":
        return "Reservation is approved and recorded."
    if status == "declined":
        return "Reservation was declined by administrator."
    if status == "cancelled":
        return "Booking flow was cancelled."
    return ""


def _booking_progress(status: str, pending_field: str | None, collected: dict[str, Any]) -> dict[str, Any]:
    total_steps = len(BOOKING_FIELDS) + 1  # +1 for review/confirm step
    completed_fields = [field for field in BOOKING_FIELDS if str(collected.get(field, "")).strip()]
    completed_count = len(completed_fields)

    if status in {"pending", "approved", "declined"}:
        done_steps = total_steps
        current_step = total_steps
    elif status == "review":
        done_steps = len(BOOKING_FIELDS)
        current_step = total_steps
    elif status == "cancelled":
        done_steps = 0
        current_step = 0
    else:
        done_steps = completed_count
        current_step = min(completed_count + 1, total_steps)

    percent = int((done_steps / total_steps) * 100) if total_steps else 0
    return {
        "current_step": current_step,
        "total_steps": total_steps,
        "percent": percent,
        "pending_field": pending_field,
        "completed_fields": completed_fields,
        "status_label": STATUS_LABELS.get(status, status),
    }


def _render_review_summary(collected: dict[str, Any]) -> str:
    lines = ["Please review your booking details:"]
    for field in BOOKING_FIELDS:
        value = str(collected.get(field, "")).strip() or "(missing)"
        lines.append(f"- {FIELD_LABELS[field]}: {value}")
    lines.append("Send 'confirm' to submit, 'edit <field>' to change, or 'cancel booking'.")
    return "\n".join(lines)


def _is_confirm_command(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in CONFIRM_COMMANDS or lowered.startswith("confirm ")


def _is_cancel_command(text: str) -> bool:
    lowered = text.strip().lower()
    if "cancel booking" in lowered:
        return True
    return lowered in CANCEL_COMMANDS


def _extract_edit_field(text: str) -> str | None:
    lowered = text.strip().lower()
    match = re.match(r"^(?:edit|change|update|correct)\s+([a-z_ ]+)$", lowered)
    if not match:
        return None
    raw = match.group(1).strip().replace(" ", "_")
    aliases = {
        "name": "name",
        "surname": "surname",
        "car": "car_number",
        "plate": "car_number",
        "car_number": "car_number",
        "period": "reservation_period",
        "reservation_period": "reservation_period",
    }
    return aliases.get(raw)


def _booking_response(
    *,
    response: str,
    status: str,
    pending_field: str | None,
    collected: dict[str, Any],
    request_id: str | None = None,
    action_required: str | None = None,
    review_summary: str | None = None,
    alternatives: list[str] | None = None,
    decided_at: str | None = None,
    recorded: bool | None = None,
    mcp_recorded: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "response": response,
        "mode": "booking",
        "status": status,
        "pending_field": pending_field,
        "collected": dict(collected),
        "progress": _booking_progress(status, pending_field, collected),
        "status_detail": _status_detail(status, collected),
    }
    if request_id:
        payload["request_id"] = request_id
    if action_required:
        payload["action_required"] = action_required
    if review_summary:
        payload["review_summary"] = review_summary
    if alternatives:
        payload["alternatives"] = alternatives
    if decided_at:
        payload["decided_at"] = decided_at
    if recorded is not None:
        payload["recorded"] = bool(recorded)
    if mcp_recorded is not None:
        payload["mcp_recorded"] = bool(mcp_recorded)
    return payload


def default_state() -> dict[str, Any]:
    return {
        "mode": "info",
        "booking_active": False,
        "pending_field": None,
        "collected": {},
        "request_id": None,
        "status": "collecting",
        "recorded": False,
        "mcp_recorded": False,
        "decided_at": None,
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
    record_reservation: Callable[..., str] | None = None,
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
    mcp_recorded = bool(current.get("mcp_recorded", False))

    if booking_active and _is_cancel_command(text):
        next_state = _state_with(
            current,
            mode="info",
            booking_active=False,
            pending_field=None,
            collected={},
            request_id=None,
            status="cancelled",
            recorded=False,
            mcp_recorded=False,
            decided_at=None,
        )
        return (
            {
                "response": "Booking cancelled. You can start a new reservation anytime.",
                "mode": "info",
                "status": "cancelled",
            },
            next_state,
        )

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
            mcp_recorded=False,
            decided_at=None,
        )
        return (
            _booking_response(
                response=FIELD_PROMPTS["name"],
                status="collecting",
                pending_field="name",
                collected={},
                action_required="input",
                recorded=False,
                mcp_recorded=False,
            ),
            next_state,
        )

    if booking_active and status == "pending" and request_id:
        approval = persistence.get_approval(request_id)
        decision = approval.get("decision") if approval else None

        if decision and decision.get("approved") is True:
            approval_time = decision.get("decided_at") or datetime.now(timezone.utc).isoformat()
            if not recorded:
                persistence.append_reservation(
                    name=f"{collected.get('name', '').strip()} {collected.get('surname', '').strip()}".strip(),
                    car_number=collected.get("car_number", ""),
                    reservation_period=collected.get("reservation_period", ""),
                    approval_time=approval_time,
                    request_id=request_id,
                )
            recorder_error: str | None = None
            if record_reservation is not None and not mcp_recorded:
                try:
                    record_reservation(
                        name=f"{collected.get('name', '').strip()} {collected.get('surname', '').strip()}".strip(),
                        car_number=collected.get("car_number", ""),
                        reservation_period=collected.get("reservation_period", ""),
                        approval_time=approval_time,
                    )
                    mcp_recorded = True
                except Exception as exc:  # pragma: no cover - best-effort side effect
                    recorder_error = str(exc)
            next_state = _state_with(
                current,
                response="Confirmed and recorded.",
                mode="booking",
                booking_active=False,
                pending_field=None,
                status="approved",
                recorded=True,
                mcp_recorded=mcp_recorded,
                decided_at=approval_time,
            )
            payload = _booking_response(
                response="Confirmed and recorded.",
                status="approved",
                pending_field=None,
                collected=collected,
                request_id=request_id,
                action_required="none",
                decided_at=approval_time,
                recorded=True,
                mcp_recorded=mcp_recorded,
            )
            if recorder_error:
                payload["status_detail"] = (
                    f"{payload.get('status_detail', '').strip()} "
                    f"(MCP file record failed: {recorder_error})"
                ).strip()
            return (payload, next_state)

        if decision and decision.get("approved") is False:
            declined_at = decision.get("decided_at")
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=False,
                pending_field=None,
                status="declined",
                recorded=False,
                mcp_recorded=mcp_recorded,
                decided_at=declined_at,
            )
            return (
                _booking_response(
                    response="Declined by administrator.",
                    status="declined",
                    pending_field=None,
                    collected=collected,
                    request_id=request_id,
                    action_required="none",
                    decided_at=declined_at,
                    recorded=False,
                    mcp_recorded=mcp_recorded,
                ),
                next_state,
            )

        next_state = _state_with(
            current,
            mode="booking",
            booking_active=True,
            pending_field=None,
            status="pending",
            mcp_recorded=mcp_recorded,
            decided_at=None,
        )
        return (
            _booking_response(
                response=f"Still pending administrator decision. Request id: {request_id}",
                status="pending",
                pending_field=None,
                collected=collected,
                request_id=request_id,
                action_required="await_admin_decision",
                recorded=recorded,
                mcp_recorded=mcp_recorded,
            ),
            next_state,
        )

    if booking_active and status == "review":
        if _is_confirm_command(text):
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
                mcp_recorded=False,
                decided_at=None,
            )
            return (
                _booking_response(
                    response=f"Submitted for approval. Request id: {new_request_id}",
                    status="pending",
                    pending_field=None,
                    collected=collected,
                    request_id=new_request_id,
                    action_required="await_admin_decision",
                    recorded=False,
                    mcp_recorded=False,
                ),
                next_state,
            )

        parsed = parse_structured_details(text)
        if parsed:
            updated = apply_valid_parsed_details(collected, parsed)
            missing = next_missing_field(updated)
            if missing:
                next_state = _state_with(
                    current,
                    mode="booking",
                    booking_active=True,
                    pending_field=missing,
                    collected=updated,
                    status="collecting",
                    recorded=False,
                    mcp_recorded=False,
                )
                return (
                    _booking_response(
                        response=FIELD_PROMPTS[missing],
                        status="collecting",
                        pending_field=missing,
                        collected=updated,
                        action_required="input",
                        recorded=False,
                        mcp_recorded=False,
                    ),
                    next_state,
                )
            summary = _render_review_summary(updated)
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=True,
                pending_field=None,
                collected=updated,
                status="review",
                recorded=False,
                mcp_recorded=False,
            )
            return (
                _booking_response(
                    response=summary,
                    status="review",
                    pending_field=None,
                    collected=updated,
                    action_required="review_confirmation",
                    review_summary=summary,
                    recorded=False,
                    mcp_recorded=False,
                ),
                next_state,
            )

        edit_field = _extract_edit_field(text)
        if edit_field:
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=True,
                pending_field=edit_field,
                collected=collected,
                status="collecting",
                recorded=recorded,
                mcp_recorded=mcp_recorded,
            )
            return (
                _booking_response(
                    response=FIELD_PROMPTS[edit_field],
                    status="collecting",
                    pending_field=edit_field,
                    collected=collected,
                    action_required="input",
                    recorded=recorded,
                    mcp_recorded=mcp_recorded,
                ),
                next_state,
            )

        summary = _render_review_summary(collected)
        return (
            _booking_response(
                response=summary,
                status="review",
                pending_field=None,
                collected=collected,
                action_required="review_confirmation",
                review_summary=summary,
                recorded=recorded,
                mcp_recorded=mcp_recorded,
            ),
            current,
        )

    if booking_active and pending_field:
        parsed = parse_structured_details(text)
        if parsed:
            collected = apply_valid_parsed_details(collected, parsed)
            pending_field = next_missing_field(collected)
            if pending_field is None:
                summary = _render_review_summary(collected)
                next_state = _state_with(
                    current,
                    mode="booking",
                    booking_active=True,
                    pending_field=None,
                    collected=collected,
                    request_id=None,
                    status="review",
                    recorded=False,
                    mcp_recorded=False,
                    decided_at=None,
                )
                return (
                    _booking_response(
                        response=summary,
                        status="review",
                        pending_field=None,
                        collected=collected,
                        action_required="review_confirmation",
                        review_summary=summary,
                        recorded=False,
                        mcp_recorded=False,
                    ),
                    next_state,
                )
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=True,
                pending_field=pending_field,
                collected=collected,
                status="collecting",
                recorded=recorded,
                mcp_recorded=mcp_recorded,
            )
            return (
                _booking_response(
                    response=FIELD_PROMPTS[pending_field],
                    status="collecting",
                    pending_field=pending_field,
                    collected=collected,
                    action_required="input",
                    recorded=recorded,
                    mcp_recorded=mcp_recorded,
                ),
                next_state,
            )

        error = validate_field(pending_field, text)
        if error:
            suggestions: list[str] = []
            if pending_field == "reservation_period":
                dynamic = get_dynamic_info()
                suggestions = suggest_alternative_periods(text, dynamic.working_hours)
                if suggestions:
                    error = f"{error} Try: {' OR '.join(suggestions)}."
            next_state = _state_with(
                current,
                mode="booking",
                booking_active=True,
                pending_field=pending_field,
                collected=collected,
                status="collecting",
                recorded=recorded,
                mcp_recorded=mcp_recorded,
            )
            return (
                _booking_response(
                    response=f"Invalid {pending_field}: {error} {FIELD_PROMPTS[pending_field]}",
                    status="collecting",
                    pending_field=pending_field,
                    collected=collected,
                    action_required="input",
                    alternatives=suggestions or None,
                    recorded=recorded,
                    mcp_recorded=mcp_recorded,
                ),
                next_state,
            )

        if pending_field == "reservation_period":
            dynamic = get_dynamic_info()
            within_hours = is_period_within_working_hours(text, dynamic.working_hours)
            if within_hours is False:
                suggestions = suggest_alternative_periods(text, dynamic.working_hours)
                next_state = _state_with(
                    current,
                    mode="booking",
                    booking_active=True,
                    pending_field=pending_field,
                    collected=collected,
                    status="collecting",
                    recorded=recorded,
                    mcp_recorded=mcp_recorded,
                )
                error_text = (
                    f"Requested time is outside working hours ({dynamic.working_hours}). "
                    f"Try: {' OR '.join(suggestions)}."
                    if suggestions
                    else f"Requested time is outside working hours ({dynamic.working_hours})."
                )
                return (
                    _booking_response(
                        response=error_text + f" {FIELD_PROMPTS[pending_field]}",
                        status="collecting",
                        pending_field=pending_field,
                        collected=collected,
                        action_required="input",
                        alternatives=suggestions or None,
                        recorded=recorded,
                        mcp_recorded=mcp_recorded,
                    ),
                    next_state,
                )

            if dynamic.available_spaces <= 0:
                suggestions = suggest_alternative_periods(text, dynamic.working_hours)
                next_state = _state_with(
                    current,
                    mode="booking",
                    booking_active=True,
                    pending_field=pending_field,
                    collected=collected,
                    status="collecting",
                    recorded=recorded,
                    mcp_recorded=mcp_recorded,
                )
                unavailable_text = "No spaces are currently available for that period."
                if suggestions:
                    unavailable_text = unavailable_text + f" Suggested alternatives: {' OR '.join(suggestions)}."
                return (
                    _booking_response(
                        response=unavailable_text + f" {FIELD_PROMPTS[pending_field]}",
                        status="collecting",
                        pending_field=pending_field,
                        collected=collected,
                        action_required="input",
                        alternatives=suggestions or None,
                        recorded=recorded,
                        mcp_recorded=mcp_recorded,
                    ),
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
                recorded=recorded,
                mcp_recorded=mcp_recorded,
            )
            return (
                _booking_response(
                    response=FIELD_PROMPTS[next_field],
                    status="collecting",
                    pending_field=next_field,
                    collected=collected,
                    action_required="input",
                    recorded=recorded,
                    mcp_recorded=mcp_recorded,
                ),
                next_state,
            )

        summary = _render_review_summary(collected)
        next_state = _state_with(
            current,
            mode="booking",
            booking_active=True,
            pending_field=None,
            collected=collected,
            request_id=None,
            status="review",
            recorded=False,
            mcp_recorded=False,
            decided_at=None,
        )
        return (
            _booking_response(
                response=summary,
                status="review",
                pending_field=None,
                collected=collected,
                action_required="review_confirmation",
                review_summary=summary,
                recorded=False,
                mcp_recorded=False,
            ),
            next_state,
        )

    try:
        response = answer_question(text)
    except Exception:
        response = (
            "I cannot answer right now because the AI provider is unavailable. "
            "Please retry in a moment or start a booking request."
        )
    next_state = _state_with(
        current,
        mode="info",
        booking_active=False,
        pending_field=None,
        collected={},
        request_id=None,
        status="collecting",
        recorded=False,
        mcp_recorded=False,
        decided_at=None,
    )
    return (
        {
            "response": response,
            "mode": "info",
            "status": "collecting",
        },
        next_state,
    )
