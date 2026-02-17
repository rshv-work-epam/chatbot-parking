"""Human-in-the-loop admin agent simulation with MCP tool integration."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import time
import uuid
from typing import Optional
from urllib import request

from langchain_core.tools import tool

from chatbot_parking.chatbot import ReservationRequest


@dataclass
class AdminDecision:
    approved: bool
    decided_at: str
    notes: Optional[str] = None


# In-memory store for pending approval requests (MCP-based)
PENDING_REQUESTS = {}


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


def request_admin_approval_mcp(
    name: str, surname: str, car_number: str, reservation_period: str
) -> dict:
    """Request approval via the MCP admin approvals system."""
    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    PENDING_REQUESTS[request_id] = {
        "payload": {
            "name": name,
            "surname": surname,
            "car_number": car_number,
            "reservation_period": reservation_period,
        },
        "decision": None,
        "created_at": now,
        "decided_at": None,
    }

    return {
        "status": "pending",
        "request_id": request_id,
        "message": "Request submitted for admin approval. Awaiting decision.",
    }


def get_pending_approvals_mcp() -> list[dict]:
    """Get pending approval requests from MCP system."""
    pending = [
        {"request_id": rid, **req}
        for rid, req in PENDING_REQUESTS.items()
        if req["decision"] is None
    ]
    return pending


def submit_approval_decision_mcp(
    request_id: str, approved: bool, notes: str = ""
) -> dict:
    """Submit an admin decision via the MCP system."""
    if request_id not in PENDING_REQUESTS:
        return {"error": "Request not found", "request_id": request_id}

    now = datetime.now(timezone.utc).isoformat()
    PENDING_REQUESTS[request_id]["decision"] = "approved" if approved else "declined"
    PENDING_REQUESTS[request_id]["decided_at"] = now
    PENDING_REQUESTS[request_id]["notes"] = notes

    return {
        "status": "decided",
        "request_id": request_id,
        "approved": approved,
        "decided_at": now,
    }


def request_admin_approval(reservation: ReservationRequest) -> AdminDecision:
    """
    Submit a reservation to the admin system (either via MCP or HTTP API when configured).
    """
    admin_url = os.getenv("ADMIN_API_URL")
    auto_approve = os.getenv("ADMIN_AUTO_APPROVE", "false").lower() == "true"
    poll_interval = float(os.getenv("ADMIN_POLL_INTERVAL", "1.0"))
    poll_timeout = float(os.getenv("ADMIN_POLL_TIMEOUT", "10.0"))

    if admin_url:
        print("[admin_agent] Using external admin API flow")
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
                decision = _get_json(f"{admin_url.rstrip('/')}/admin/decisions/{request_id}")
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

    # Use MCP admin approvals system (in-process)
    try:
        print("[admin_agent] Using in-process MCP admin approval flow")
        approval_result = request_admin_approval_mcp(
            name=reservation.name,
            surname=reservation.surname,
            car_number=reservation.car_number,
            reservation_period=reservation.reservation_period,
        )
        request_id = approval_result.get("request_id")

        if auto_approve:
            decision_result = submit_approval_decision_mcp(
                request_id=request_id,
                approved=True,
                notes="Auto-approved via demo client",
            )
            return AdminDecision(
                approved=decision_result.get("approved", True),
                decided_at=decision_result.get(
                    "decided_at", datetime.now(timezone.utc).isoformat()
                ),
                notes="Auto-approved via demo client",
            )

        deadline = datetime.now(timezone.utc).timestamp() + poll_timeout
        while datetime.now(timezone.utc).timestamp() < deadline:
            request_entry = PENDING_REQUESTS.get(request_id)
            if request_entry and request_entry.get("decision") is not None:
                return AdminDecision(
                    approved=request_entry["decision"] == "approved",
                    decided_at=request_entry.get(
                        "decided_at", datetime.now(timezone.utc).isoformat()
                    ),
                    notes=request_entry.get("notes", ""),
                )
            time.sleep(poll_interval)

        decided_at = datetime.now(timezone.utc).isoformat()
        return AdminDecision(
            approved=False,
            decided_at=decided_at,
            notes="No admin decision received before timeout.",
        )
    except Exception:
        decided_at = datetime.now(timezone.utc).isoformat()
        return AdminDecision(
            approved=True,
            decided_at=decided_at,
            notes="Auto-approved for demo (MCP error fallback)",
        )


@tool
def request_admin_approval_tool(
    name: str, surname: str, car_number: str, reservation_period: str
) -> dict:
    """LangChain tool wrapper for admin approval of a reservation via MCP."""
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
