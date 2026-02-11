"""MCP server for admin parking reservation approvals."""

from datetime import datetime, timezone
import json
import os
import uuid

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.types as types


# Initialize the MCP server
server = Server("parking-admin-approvals")

# In-memory store for pending approval requests
# Format: {request_id: {"payload": {...}, "decision": None or "approved"/"declined", "created_at": "...", "decided_at": "..."}}
PENDING_REQUESTS = {}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise the admin approval tools."""
    return [
        Tool(
            name="request_admin_approval",
            description="Request admin approval for a parking reservation via the admin approval system",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Guest first name",
                    },
                    "surname": {
                        "type": "string",
                        "description": "Guest last name",
                    },
                    "car_number": {
                        "type": "string",
                        "description": "Vehicle license plate",
                    },
                    "reservation_period": {
                        "type": "string",
                        "description": "Desired parking period",
                    },
                },
                "required": ["name", "surname", "car_number", "reservation_period"],
            },
        ),
        Tool(
            name="get_pending_approvals",
            description="Get list of pending approval requests awaiting admin decision",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="submit_approval_decision",
            description="Submit an admin decision (approve or decline) for a pending request",
            inputSchema={
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "The ID of the request to decide on",
                    },
                    "approved": {
                        "type": "boolean",
                        "description": "True to approve, False to decline",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional admin notes/reason for decision",
                    },
                },
                "required": ["request_id", "approved"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls for admin approval workflow."""

    if name == "request_admin_approval":
        request_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        PENDING_REQUESTS[request_id] = {
            "payload": {
                "name": arguments["name"],
                "surname": arguments["surname"],
                "car_number": arguments["car_number"],
                "reservation_period": arguments["reservation_period"],
            },
            "decision": None,
            "created_at": now,
            "decided_at": None,
        }

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "pending",
                        "request_id": request_id,
                        "message": "Request submitted for admin approval. Awaiting decision.",
                    }
                ),
            )
        ]

    elif name == "get_pending_approvals":
        pending = [
            {"request_id": rid, **req}
            for rid, req in PENDING_REQUESTS.items()
            if req["decision"] is None
        ]
        return [TextContent(type="text", text=json.dumps(pending))]

    elif name == "submit_approval_decision":
        request_id = arguments["request_id"]
        if request_id not in PENDING_REQUESTS:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": "Request not found", "request_id": request_id}
                    ),
                )
            ]

        now = datetime.now(timezone.utc).isoformat()
        PENDING_REQUESTS[request_id]["decision"] = (
            "approved" if arguments["approved"] else "declined"
        )
        PENDING_REQUESTS[request_id]["decided_at"] = now
        PENDING_REQUESTS[request_id]["notes"] = arguments.get("notes", "")

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "decided",
                        "request_id": request_id,
                        "approved": arguments["approved"],
                        "decided_at": now,
                    }
                ),
            )
        ]

    else:
        raise ValueError(f"Unknown tool: {name}")
