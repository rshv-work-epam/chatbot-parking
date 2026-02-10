"""Admin REST API for approving or rejecting reservations."""

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from chatbot_parking.chatbot import ReservationRequest

app = FastAPI(title="Parking Admin API")

PENDING: Dict[str, ReservationRequest] = {}
DECISIONS: Dict[str, dict] = {}


def _require_admin_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("ADMIN_API_TOKEN")
    if expected and x_api_token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin API token")


class AdminRequest(BaseModel):
    name: str
    surname: str
    car_number: str
    reservation_period: str


class AdminDecisionPayload(BaseModel):
    request_id: str
    approved: bool
    notes: Optional[str] = None


@app.get("/admin/health")
def health() -> dict:
    return {"status": "ok", "service": "admin_api"}


@app.post("/admin/request")
def submit_request(payload: AdminRequest, _auth: None = Depends(_require_admin_token)) -> dict:
    request_id = uuid4().hex
    reservation = ReservationRequest(**payload.model_dump())
    PENDING[request_id] = reservation
    return {"request_id": request_id, "status": "pending"}


@app.post("/admin/decision")
def submit_decision(payload: AdminDecisionPayload, _auth: None = Depends(_require_admin_token)) -> dict:
    reservation = PENDING.pop(payload.request_id, None)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Request not found")
    decision = {
        "approved": payload.approved,
        "notes": payload.notes,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "reservation": asdict(reservation),
    }
    DECISIONS[payload.request_id] = decision
    return {"request_id": payload.request_id, **decision}


@app.get("/admin/requests/{request_id}")
def get_request(request_id: str, _auth: None = Depends(_require_admin_token)) -> dict:
    reservation = PENDING.get(request_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"request_id": request_id, "reservation": asdict(reservation)}


@app.get("/admin/requests")
def list_requests(_auth: None = Depends(_require_admin_token)) -> dict:
    return {
        "pending": [
            {"request_id": request_id, "reservation": asdict(reservation)}
            for request_id, reservation in PENDING.items()
        ]
    }


@app.get("/admin/decisions/{request_id}")
def get_decision(request_id: str, _auth: None = Depends(_require_admin_token)) -> dict:
    decision = DECISIONS.get(request_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"request_id": request_id, **decision}
