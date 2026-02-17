"""MCP server for parking reservation recording."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.types as types


# Initialize the MCP server
server = Server("parking-reservations")
REPO_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "reservations.txt"
TMP_DATA_PATH = Path("/tmp/reservations.txt")
DEFAULT_DATA_PATH = TMP_DATA_PATH


def _resolve_data_path() -> Path:
    env = os.getenv("RESERVATIONS_FILE_PATH")
    if env:
        return Path(env)

    # Default to /tmp to avoid mutating checked-in sample files; fall back to repo-local when needed.
    for candidate in (DEFAULT_DATA_PATH, REPO_DATA_PATH):
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if os.access(candidate.parent, os.W_OK):
                return candidate
        except Exception:
            continue

    return TMP_DATA_PATH


def append_reservation_record(
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str,
) -> None:
    """Write reservation record to file."""
    line = f"{name} | {car_number} | {reservation_period} | {approval_time}\n"
    data_path = _resolve_data_path()
    with data_path.open("a", encoding="utf-8") as handle:
        handle.write(line)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise the reservation recording tool."""
    return [
        Tool(
            name="record_reservation",
            description="Record a confirmed parking reservation with guest details and reservation period",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Guest full name (first and last name)",
                    },
                    "car_number": {
                        "type": "string",
                        "description": "Vehicle license plate number",
                    },
                    "reservation_period": {
                        "type": "string",
                        "description": "Parking period (e.g., '2026-02-20 09:00 to 2026-02-20 18:00')",
                    },
                    "approval_time": {
                        "type": "string",
                        "description": "ISO timestamp when reservation was approved (optional; auto-generated if not provided)",
                    },
                },
                "required": ["name", "car_number", "reservation_period"],
            },
        )
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls for reservation recording."""
    if name != "record_reservation":
        raise ValueError(f"Unknown tool: {name}")

    approval_time = arguments.get("approval_time") or datetime.now(
        timezone.utc
    ).isoformat()

    # Record to file
    append_reservation_record(
        name=arguments["name"],
        car_number=arguments["car_number"],
        reservation_period=arguments["reservation_period"],
        approval_time=approval_time,
    )

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "status": "stored",
                    "name": arguments["name"],
                    "car_number": arguments["car_number"],
                    "reservation_period": arguments["reservation_period"],
                    "approval_time": approval_time,
                }
            ),
        )
    ]
