"""Human-in-the-loop admin agent integration."""

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Optional

import requests

from chatbot_parking.chatbot import ReservationRequest


@dataclass
class AdminDecision:
    approved: bool
    decided_at: str
    notes: Optional[str] = None


@dataclass
class AdminConfig:
    endpoint: Optional[str] = None
    api_token: Optional[str] = None
    timeout_seconds: int = 10


class AdminClient:
    def __init__(self, config: Optional[AdminConfig] = None) -> None:
        self.config = config or AdminConfig(
            endpoint=os.getenv("ADMIN_ENDPOINT"),
            api_token=os.getenv("ADMIN_API_TOKEN"),
        )

    def request_approval(self, reservation: ReservationRequest) -> AdminDecision:
        if not self.config.endpoint:
            return self._auto_approve()
        try:
            response = requests.post(
                self.config.endpoint,
                json={
                    "request_id": f"{reservation.name}-{reservation.car_number}",
                    "name": reservation.name,
                    "surname": reservation.surname,
                    "car_number": reservation.car_number,
                    "reservation_period": reservation.reservation_period,
                },
                headers={"x-api-token": self.config.api_token or ""},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return AdminDecision(
                approved=bool(payload.get("approved", False)),
                decided_at=payload.get("decided_at", datetime.now(timezone.utc).isoformat()),
                notes=payload.get("notes"),
            )
        except Exception:
            return self._auto_approve()

    def _auto_approve(self) -> AdminDecision:
        decided_at = datetime.now(timezone.utc).isoformat()
        return AdminDecision(approved=True, decided_at=decided_at, notes="Auto-approved fallback")


def request_admin_approval(reservation: ReservationRequest) -> AdminDecision:
    """Convenience wrapper for the configured admin client."""
    return AdminClient().request_approval(reservation)
