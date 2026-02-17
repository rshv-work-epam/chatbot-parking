"""Admin REST API for approving or rejecting reservations."""

from typing import Optional

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from chatbot_parking.admin_store import (
    create_admin_request,
    get_admin_decision,
    get_admin_request,
    list_pending_requests,
    post_admin_decision,
)

app = FastAPI(title="Parking Admin API")


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
    request_id = create_admin_request(payload.model_dump())
    return {"request_id": request_id, "status": "pending"}


@app.post("/admin/decision")
def submit_decision(payload: AdminDecisionPayload, _auth: None = Depends(_require_admin_token)) -> dict:
    decision = post_admin_decision(
        request_id=payload.request_id,
        approved=payload.approved,
        notes=payload.notes,
    )
    if decision is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"request_id": payload.request_id, **decision}


@app.get("/admin/requests/{request_id}")
def get_request(request_id: str, _auth: None = Depends(_require_admin_token)) -> dict:
    reservation = get_admin_request(request_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"request_id": request_id, "reservation": reservation.get("payload", {})}


@app.get("/admin/requests")
def list_requests(_auth: None = Depends(_require_admin_token)) -> dict:
    return {"pending": list_pending_requests()}


@app.get("/admin/decisions/{request_id}")
def get_decision(request_id: str, _auth: None = Depends(_require_admin_token)) -> dict:
    decision = get_admin_decision(request_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"request_id": request_id, **decision}
