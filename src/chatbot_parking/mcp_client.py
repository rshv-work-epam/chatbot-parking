"""Client utilities for recording reservations via MCP server."""

from datetime import datetime, timezone

from chatbot_parking.mcp_servers.reservations_server import append_reservation_record


def record_reservation(
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str | None = None,
) -> str:
    """Record a parking reservation via the MCP reservations server."""
    approval_time = approval_time or datetime.now(timezone.utc).isoformat()

    # Call the MCP server's underlying function directly
    append_reservation_record(
        name=name,
        car_number=car_number,
        reservation_period=reservation_period,
        approval_time=approval_time,
    )

    return approval_time
