"""Admin REST API for approving or rejecting reservations."""

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from chatbot_parking.chatbot import ReservationRequest

app = FastAPI(title="Parking Admin API")

PENDING: Dict[str, ReservationRequest] = {}
DECISIONS: Dict[str, dict] = {}


class AdminRequest(BaseModel):
    name: str
    surname: str
    car_number: str
    reservation_period: str


class AdminDecisionPayload(BaseModel):
    request_id: str
    approved: bool
    notes: Optional[str] = None


@app.post("/admin/request")
def submit_request(payload: AdminRequest) -> dict:
    request_id = uuid4().hex
    reservation = ReservationRequest(**payload.model_dump())
    PENDING[request_id] = reservation
    return {"request_id": request_id, "status": "pending"}


@app.post("/admin/decision")
def submit_decision(payload: AdminDecisionPayload) -> dict:
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
def get_request(request_id: str) -> dict:
    reservation = PENDING.get(request_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"request_id": request_id, "reservation": asdict(reservation)}


@app.get("/admin/decisions/{request_id}")
def get_decision(request_id: str) -> dict:
    decision = DECISIONS.get(request_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"request_id": request_id, **decision}
