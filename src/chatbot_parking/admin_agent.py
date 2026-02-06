"""Human-in-the-loop admin agent simulation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from chatbot_parking.chatbot import ReservationRequest


@dataclass
class AdminDecision:
    approved: bool
    decided_at: str
    notes: Optional[str] = None


def request_admin_approval(reservation: ReservationRequest) -> AdminDecision:
    """
    Simulate admin approval. Replace with email, messenger, or REST integration.
    """
    approval = True
    decided_at = datetime.now(timezone.utc).isoformat()
    return AdminDecision(approved=approval, decided_at=decided_at, notes="Auto-approved for demo")
