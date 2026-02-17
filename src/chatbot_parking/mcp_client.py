"""Client utilities for recording reservations via a real MCP protocol client."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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

    env = dict(os.environ)
    # Ensure the MCP server process can import the package when running from source.
    src_dir = Path(__file__).resolve().parents[1]
    existing = env.get("PYTHONPATH", "")
    paths = [p for p in existing.split(os.pathsep) if p]
    if str(src_dir) not in paths:
        paths.insert(0, str(src_dir))
        env["PYTHONPATH"] = os.pathsep.join(paths)

    params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
        cwd=os.getcwd(),
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


def record_reservation(
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str | None = None,
) -> str:
    """Record a parking reservation via MCP stdio tool invocation."""

    approval_time = approval_time or datetime.now(timezone.utc).isoformat()
    ok = asyncio.run(
        _record_via_mcp_stdio(
            name=name,
            car_number=car_number,
            reservation_period=reservation_period,
            approval_time=approval_time,
        )
    )
    if not ok:
        raise RuntimeError("Reservation write failed via MCP stdio tool call")
    return approval_time
