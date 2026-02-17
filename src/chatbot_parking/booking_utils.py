"""Utilities for booking intent detection and reservation field validation/parsing."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import re
from typing import Any

BOOKING_FIELDS: list[str] = ["name", "surname", "car_number", "reservation_period"]

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z' -]{1,49}$")
CAR_RE = re.compile(r"^[A-Z0-9-]{4,12}$")
PERIOD_RE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+to\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*$",
    re.IGNORECASE,
)
BOOKING_KEYWORDS = [
    "book",
    "booking",
    "reserve",
    "reservation",
    "parking spot",
    "parking place",
    "бронь",
    "броню",
    "заброню",
    "забронювати",
]


def is_booking_keyword_intent(message: str) -> bool:
    lowered = message.lower()
    return any(word in lowered for word in BOOKING_KEYWORDS)


def _parse_period_or_none(value: str) -> tuple[datetime, datetime] | None:
    match = PERIOD_RE.match(value)
    if not match:
        return None
    start = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")
    end = datetime.strptime(match.group(2), "%Y-%m-%d %H:%M")
    return (start, end)


def parse_reservation_period(value: str) -> tuple[datetime, datetime] | None:
    return _parse_period_or_none(value)


def parse_working_hours_window(working_hours: str) -> tuple[time, time] | None:
    match = re.search(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", working_hours)
    if not match:
        return None
    start_hour = datetime.strptime(match.group(1), "%H:%M").time()
    end_hour = datetime.strptime(match.group(2), "%H:%M").time()
    return (start_hour, end_hour)


def is_period_within_working_hours(period: str, working_hours: str) -> bool | None:
    parsed_period = parse_reservation_period(period)
    hours_window = parse_working_hours_window(working_hours)
    if not parsed_period or not hours_window:
        return None
    start, end = parsed_period
    open_at, close_at = hours_window
    return start.time() >= open_at and end.time() <= close_at


def suggest_alternative_periods(period: str, working_hours: str) -> list[str]:
    parsed = parse_reservation_period(period)
    hours_window = parse_working_hours_window(working_hours)
    if not parsed or not hours_window:
        return []

    start, end = parsed
    open_at, close_at = hours_window
    duration = end - start
    if duration.total_seconds() <= 0:
        duration = timedelta(hours=1)

    same_day_open = start.replace(hour=open_at.hour, minute=open_at.minute, second=0, microsecond=0)
    same_day_close = start.replace(hour=close_at.hour, minute=close_at.minute, second=0, microsecond=0)

    suggestions: list[tuple[datetime, datetime]] = []

    proposed_start = max(start, same_day_open)
    proposed_end = proposed_start + duration
    if proposed_end <= same_day_close:
        suggestions.append((proposed_start, proposed_end))

    next_day_start = (start + timedelta(days=1)).replace(
        hour=open_at.hour,
        minute=open_at.minute,
        second=0,
        microsecond=0,
    )
    next_day_end = next_day_start + duration
    next_day_close = next_day_start.replace(hour=close_at.hour, minute=close_at.minute)
    if next_day_end > next_day_close:
        next_day_end = next_day_close
    if next_day_end > next_day_start:
        suggestions.append((next_day_start, next_day_end))

    rendered: list[str] = []
    for candidate_start, candidate_end in suggestions:
        normalized = (
            f"{candidate_start.strftime('%Y-%m-%d %H:%M')} "
            f"to {candidate_end.strftime('%Y-%m-%d %H:%M')}"
        )
        if normalized not in rendered:
            rendered.append(normalized)

    return rendered[:2]


def validate_field(field: str, value: str) -> str | None:
    if field in {"name", "surname"}:
        if not NAME_RE.fullmatch(value):
            return "Use only letters, spaces, apostrophe, or hyphen (2-50 chars)."
        return None

    if field == "car_number":
        normalized = normalize_car_number(value)
        if not CAR_RE.fullmatch(normalized):
            return "Car number must be 4-12 chars: letters, digits, or '-' only."
        return None

    if field == "reservation_period":
        period = _parse_period_or_none(value)
        if period is None:
            return "Use format: YYYY-MM-DD HH:MM to YYYY-MM-DD HH:MM."
        start, end = period
        if end <= start:
            return "Reservation end time must be after start time."
        return None

    return None


def normalize_car_number(value: str) -> str:
    return value.upper().replace(" ", "")


def normalize_reservation_period(value: str) -> str:
    parsed = _parse_period_or_none(value)
    if parsed is None:
        return value.strip()
    start, end = parsed
    return f"{start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')}"


def parse_structured_details(text: str) -> dict[str, str]:
    """Parse booking details from free-form but structured-like user input."""
    result: dict[str, str] = {}
    value = text.strip()

    patterns = {
        "name": r"(?:^|[\s,;])name[:=]\s*([A-Za-z][A-Za-z' -]{1,49})",
        "surname": r"(?:^|[\s,;])surname[:=]\s*([A-Za-z][A-Za-z' -]{1,49})",
        "car_number": r"(?:^|[\s,;])(?:car|plate|car_number)[:=]\s*([A-Za-z0-9 -]{4,20})",
        "reservation_period": r"(?:^|[\s,;])(?:period|reservation_period)[:=]\s*([^;]+)$",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()

    return result


def apply_valid_parsed_details(collected: dict[str, str], parsed: dict[str, str]) -> dict[str, str]:
    merged = dict(collected)
    for field in BOOKING_FIELDS:
        raw = parsed.get(field)
        if not raw:
            continue
        if validate_field(field, raw):
            continue
        if field == "car_number":
            merged[field] = normalize_car_number(raw)
        elif field == "reservation_period":
            merged[field] = normalize_reservation_period(raw)
        else:
            merged[field] = raw
    return merged


def next_missing_field(collected: dict[str, Any]) -> str | None:
    for field in BOOKING_FIELDS:
        if not str(collected.get(field, "")).strip():
            return field
    return None
