"""Parking spot modeling utilities.

This module provides deterministic helpers for:
- availability checks (based on recorded reservations)
- spot assignment (P1..PN)
- a "spot board" view for admin UI

It intentionally stays lightweight and avoids any storage concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from chatbot_parking.booking_utils import parse_reservation_period


def periods_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    # Half-open overlap check. Treat end as non-inclusive.
    return a_start < b_end and b_start < a_end


def _parse_record_period(record: dict[str, Any]) -> tuple[datetime, datetime] | None:
    # Prefer explicit start/end fields when present.
    start_at = str(record.get("start_at") or "").strip()
    end_at = str(record.get("end_at") or "").strip()
    if start_at and end_at:
        try:
            return (datetime.fromisoformat(start_at), datetime.fromisoformat(end_at))
        except Exception:
            pass

    period = str(record.get("reservation_period") or "").strip()
    if not period:
        return None
    return parse_reservation_period(period)


def count_overlapping_reservations(
    *,
    start: datetime,
    end: datetime,
    reservations: list[dict[str, Any]],
) -> int:
    count = 0
    for record in reservations:
        parsed = _parse_record_period(record)
        if not parsed:
            continue
        r_start, r_end = parsed
        if periods_overlap(start, end, r_start, r_end):
            count += 1
    return count


def choose_spot_id(
    *,
    start: datetime,
    end: datetime,
    reservations: list[dict[str, Any]],
    total_spots: int,
) -> str | None:
    """Assign the first available spot id for the given time window."""
    if total_spots <= 0:
        return None

    # Build occupancy per spot id for reservations that already have an assignment.
    occupancy: dict[str, list[tuple[datetime, datetime]]] = {
        f"P{i}": [] for i in range(1, total_spots + 1)
    }

    for record in reservations:
        spot_id = str(record.get("spot_id") or "").strip()
        if not spot_id or spot_id not in occupancy:
            continue
        parsed = _parse_record_period(record)
        if not parsed:
            continue
        occupancy[spot_id].append(parsed)

    for spot_id, windows in occupancy.items():
        if all(not periods_overlap(start, end, w_start, w_end) for w_start, w_end in windows):
            return spot_id

    return None


@dataclass(frozen=True)
class SpotBoardItem:
    spot_id: str
    status: str  # available|booked
    booked_until: str | None
    reservations: list[dict[str, Any]]


def build_spot_board(
    *,
    start: datetime,
    end: datetime,
    reservations: list[dict[str, Any]],
    total_spots: int,
) -> list[SpotBoardItem]:
    if total_spots <= 0:
        return []

    # Group reservations by spot_id when present.
    grouped: dict[str, list[dict[str, Any]]] = {f"P{i}": [] for i in range(1, total_spots + 1)}
    unassigned: list[dict[str, Any]] = []

    for record in reservations:
        spot_id = str(record.get("spot_id") or "").strip()
        if not spot_id or spot_id not in grouped:
            unassigned.append(record)
            continue
        grouped[spot_id].append(record)

    board: list[SpotBoardItem] = []
    for spot_id in grouped.keys():
        overlapping: list[dict[str, Any]] = []
        latest_end: datetime | None = None

        for record in grouped[spot_id]:
            parsed = _parse_record_period(record)
            if not parsed:
                continue
            r_start, r_end = parsed
            if not periods_overlap(start, end, r_start, r_end):
                continue
            overlapping.append(record)
            if latest_end is None or r_end > latest_end:
                latest_end = r_end

        status = "booked" if overlapping else "available"
        booked_until = latest_end.isoformat() if latest_end else None
        board.append(
            SpotBoardItem(
                spot_id=spot_id,
                status=status,
                booked_until=booked_until,
                reservations=overlapping,
            )
        )

    # Keep deterministic order P1..PN.
    return board


def default_board_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    # Use naive local time by default (matches UI inputs which are local).
    base = now or datetime.now()
    start = base.replace(second=0, microsecond=0)
    end = start + timedelta(hours=2)
    return (start, end)
