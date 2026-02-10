"""Human-in-the-loop admin agent simulation with LangChain tool wrapper."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import time
from typing import Optional
from urllib import request

from langchain_core.tools import tool

from chatbot_parking.chatbot import ReservationRequest


@dataclass
class AdminDecision:
    approved: bool
    decided_at: str
    notes: Optional[str] = None


def _build_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token = os.getenv("ADMIN_API_TOKEN")
    if token:
        headers["x-api-token"] = token
    return headers


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=_build_headers())
    with request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str) -> dict:
    req = request.Request(url, method="GET", headers=_build_headers())
    with request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def request_admin_approval(reservation: ReservationRequest) -> AdminDecision:
    """
    Submit a reservation to the admin API when configured, otherwise auto-approve.
    """
    admin_url = os.getenv("ADMIN_API_URL")
    auto_approve = os.getenv("ADMIN_AUTO_APPROVE", "true").lower() == "true"
    poll_interval = float(os.getenv("ADMIN_POLL_INTERVAL", "1.0"))
    poll_timeout = float(os.getenv("ADMIN_POLL_TIMEOUT", "10.0"))

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
        request_id = submit["request_id"]
        if auto_approve:
            decision = _post_json(
                f"{admin_url.rstrip('/')}/admin/decision",
                {
                    "request_id": request_id,
                    "approved": True,
                    "notes": "Auto-approved via demo client",
                },
            )
            return AdminDecision(
                approved=decision["approved"],
                decided_at=decision["decided_at"],
                notes=decision.get("notes"),
            )

        deadline = datetime.now(timezone.utc).timestamp() + poll_timeout
        while datetime.now(timezone.utc).timestamp() < deadline:
            try:
                decision = _get_json(
                    f"{admin_url.rstrip('/')}/admin/decisions/{request_id}"
                )
                return AdminDecision(
                    approved=decision["approved"],
                    decided_at=decision["decided_at"],
                    notes=decision.get("notes"),
                )
            except Exception:
                time.sleep(poll_interval)

        decided_at = datetime.now(timezone.utc).isoformat()
        return AdminDecision(
            approved=False,
            decided_at=decided_at,
            notes="No admin decision received before timeout.",
        )

    decided_at = datetime.now(timezone.utc).isoformat()
    return AdminDecision(approved=True, decided_at=decided_at, notes="Auto-approved for demo")


@tool
def request_admin_approval_tool(
    name: str, surname: str, car_number: str, reservation_period: str
) -> dict:
    """LangChain tool wrapper for admin approval of a reservation."""
    decision = request_admin_approval(
        ReservationRequest(
            name=name,
            surname=surname,
            car_number=car_number,
            reservation_period=reservation_period,
        )
    )
    return {
        "approved": decision.approved,
        "decided_at": decision.decided_at,
        "notes": decision.notes,
    }
