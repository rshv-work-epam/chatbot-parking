"""Client utilities for recording reservations via a real MCP protocol client."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib import request

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8001"
DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "reservations.txt"


def _append_reservation_local(
    *,
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str,
) -> None:
    line = f"{name} | {car_number} | {reservation_period} | {approval_time}\n"
    path = Path(os.getenv("RESERVATIONS_FILE_PATH", str(DEFAULT_DATA_PATH)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _parse_call_tool_result(result: Any) -> dict[str, Any]:
    content = getattr(result, "content", None) or []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    return {}


async def _record_via_mcp_stdio(
    *,
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str,
) -> bool:
    command = os.getenv("MCP_SERVER_COMMAND", sys.executable)
    args_env = os.getenv("MCP_SERVER_ARGS")
    if args_env:
        args = args_env.split()
    else:
        args = ["-m", "chatbot_parking.mcp_servers.reservations_stdio_server"]

    params = StdioServerParameters(
        command=command,
        args=args,
        env=dict(os.environ),
        cwd=Path(__file__).resolve().parents[2],
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "record_reservation",
                {
                    "name": name,
                    "car_number": car_number,
                    "reservation_period": reservation_period,
                    "approval_time": approval_time,
                },
            )
            payload = _parse_call_tool_result(result)
            return payload.get("status") == "stored"


def _record_via_http(
    *,
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str,
) -> bool:
    base_url = os.getenv("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL).rstrip("/")
    token = os.getenv("MCP_API_TOKEN")
    if not token:
        return False

    payload = {
        "name": name,
        "car_number": car_number,
        "reservation_period": reservation_period,
        "approval_time": approval_time,
    }
    req = request.Request(
        f"{base_url}/record",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-token": token,
        },
        method="POST",
    )
    with request.urlopen(req, timeout=5) as response:
        return 200 <= response.status < 300


def record_reservation(
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str | None = None,
) -> str:
    """Record a parking reservation using MCP stdio by default.

    Transport selection:
    - `MCP_TRANSPORT=stdio` (default): real MCP protocol via stdio session.
    - `MCP_TRANSPORT=http`: compatibility mode against HTTP API.

    Fallback behavior:
    - If `MCP_ALLOW_LOCAL_FALLBACK=true`, writes to local file on transport failures.
    - Otherwise transport errors are raised.
    """

    approval_time = approval_time or datetime.now(timezone.utc).isoformat()
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    allow_local_fallback = os.getenv("MCP_ALLOW_LOCAL_FALLBACK", "false").lower() == "true"

    try:
        if transport == "http":
            ok = _record_via_http(
                name=name,
                car_number=car_number,
                reservation_period=reservation_period,
                approval_time=approval_time,
            )
        else:
            ok = asyncio.run(
                _record_via_mcp_stdio(
                    name=name,
                    car_number=car_number,
                    reservation_period=reservation_period,
                    approval_time=approval_time,
                )
            )
        if ok:
            return approval_time
        raise RuntimeError("Reservation write failed via configured MCP transport")
    except Exception:
        if not allow_local_fallback:
            raise
        _append_reservation_local(
            name=name,
            car_number=car_number,
            reservation_period=reservation_period,
            approval_time=approval_time,
        )
        return approval_time
