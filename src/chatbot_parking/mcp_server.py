"""Simple MCP-like server to record confirmed reservations."""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Parking MCP Server")

DATA_PATH = Path("data/reservations.txt")
API_TOKEN = os.getenv("MCP_API_TOKEN", "change-me")


class ReservationRecord(BaseModel):
    name: str
    car_number: str
    reservation_period: str
    approval_time: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mcp_server"}


@app.post("/record")
def record_reservation(
    record: ReservationRecord,
    x_api_token: str | None = Header(default=None),
) -> dict:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    approval_time = record.approval_time or datetime.now(timezone.utc).isoformat()
    append_reservation_record(
        name=record.name,
        car_number=record.car_number,
        reservation_period=record.reservation_period,
        approval_time=approval_time,
    )
    return {"status": "stored", "approval_time": approval_time}


def append_reservation_record(
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str,
) -> None:
    line = f"{name} | {car_number} | {reservation_period} | {approval_time}\n"
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)
