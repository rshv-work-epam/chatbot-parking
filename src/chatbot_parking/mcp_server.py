"""Simple MCP-like server to record confirmed reservations."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Parking MCP Server")

DATA_PATH = Path("data/reservations.txt")
API_TOKEN = "change-me"  # replace with secret from environment in production


class ReservationRecord(BaseModel):
    name: str
    car_number: str
    reservation_period: str
    approval_time: Optional[str] = None


@app.post("/record")
def record_reservation(
    record: ReservationRecord,
    x_api_token: str | None = Header(default=None),
) -> dict:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    approval_time = record.approval_time or datetime.now(timezone.utc).isoformat()
    line = f"{record.name} | {record.car_number} | {record.reservation_period} | {approval_time}\n"
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(DATA_PATH.read_text() + line if DATA_PATH.exists() else line)
    return {"status": "stored", "approval_time": approval_time}
