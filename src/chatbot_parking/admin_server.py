"""FastAPI server for admin approval decisions."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Parking Admin Approval API")

API_TOKEN = "change-me"
PENDING_REQUESTS: dict[str, dict] = {}


class AdminRequest(BaseModel):
    request_id: str
    name: str
    surname: str
    car_number: str
    reservation_period: str


class AdminDecisionPayload(BaseModel):
    request_id: str
    approved: bool
    notes: Optional[str] = None


@app.post("/admin/request")
def create_request(
    request: AdminRequest,
    x_api_token: str | None = Header(default=None),
) -> dict:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    PENDING_REQUESTS[request.request_id] = request.model_dump()
    return {"status": "queued", "request_id": request.request_id}


@app.post("/admin/decision")
def decide_request(
    decision: AdminDecisionPayload,
    x_api_token: str | None = Header(default=None),
) -> dict:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if decision.request_id not in PENDING_REQUESTS:
        raise HTTPException(status_code=404, detail="Unknown request")
    decided_at = datetime.now(timezone.utc).isoformat()
    return {
        "approved": decision.approved,
        "decided_at": decided_at,
        "notes": decision.notes,
    }
