"""Simple MCP-like server to record confirmed reservations."""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Parking MCP Server")

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "reservations.txt"


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
    api_token = os.getenv("MCP_API_TOKEN")
    if not api_token:
        raise HTTPException(status_code=500, detail="MCP_API_TOKEN is not configured")

    if x_api_token != api_token:
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
    data_path = Path(os.getenv("RESERVATIONS_FILE_PATH", str(DEFAULT_DATA_PATH)))
    data_path.parent.mkdir(parents=True, exist_ok=True)
    with data_path.open("a", encoding="utf-8") as handle:
        handle.write(line)
