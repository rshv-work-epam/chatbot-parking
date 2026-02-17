"""Stdio entrypoint for the parking reservations MCP server."""

from __future__ import annotations

import anyio
from mcp.server.stdio import stdio_server

from chatbot_parking.mcp_servers.reservations_server import server


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
