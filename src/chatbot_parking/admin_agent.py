"""Human-in-the-loop admin agent simulation."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Optional
from urllib import request

from chatbot_parking.chatbot import ReservationRequest


@dataclass
class AdminDecision:
    approved: bool
    decided_at: str
    notes: Optional[str] = None


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def request_admin_approval(reservation: ReservationRequest) -> AdminDecision:
    """
    Submit a reservation to the admin API when configured, otherwise auto-approve.
    """
    admin_url = os.getenv("ADMIN_API_URL")
    if admin_url:
        submit = _post_json(
            f"{admin_url.rstrip('/')}/admin/request",
            {
                "name": reservation.name,
                "surname": reservation.surname,
                "car_number": reservation.car_number,
                "reservation_period": reservation.reservation_period,
            },
        )
        decision = _post_json(
            f"{admin_url.rstrip('/')}/admin/decision",
            {
                "request_id": submit["request_id"],
                "approved": True,
                "notes": "Auto-approved via demo client",
            },
        )
        return AdminDecision(
            approved=decision["approved"],
            decided_at=decision["decided_at"],
            notes=decision.get("notes"),
        )

    decided_at = datetime.now(timezone.utc).isoformat()
    return AdminDecision(approved=True, decided_at=decided_at, notes="Auto-approved for demo")
