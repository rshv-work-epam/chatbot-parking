"""Client utilities for recording reservations via MCP server."""

from datetime import datetime, timezone
import json
import os
from urllib import request

from chatbot_parking.mcp_server import append_reservation_record


def record_reservation(
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str | None = None,
) -> str:
    approval_time = approval_time or datetime.now(timezone.utc).isoformat()
    mcp_url = os.getenv("MCP_SERVER_URL")
    if mcp_url:
        payload = json.dumps(
            {
                "name": name,
                "car_number": car_number,
                "reservation_period": reservation_period,
                "approval_time": approval_time,
            }
        ).encode("utf-8")
        token = os.getenv("MCP_API_TOKEN", "change-me")
        req = request.Request(
            f"{mcp_url.rstrip('/')}/record",
            data=payload,
            headers={"Content-Type": "application/json", "x-api-token": token},
        )
        with request.urlopen(req, timeout=5) as response:
            response.read()
        return approval_time

    append_reservation_record(
        name=name,
        car_number=car_number,
        reservation_period=reservation_period,
        approval_time=approval_time,
    )
    return approval_time
