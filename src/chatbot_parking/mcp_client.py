"""Client for recording approved reservations in the MCP server."""

from dataclasses import dataclass
import os
from typing import Optional

import requests

from chatbot_parking.chatbot import ReservationRequest


@dataclass
class MCPConfig:
    endpoint: Optional[str] = None
    api_token: Optional[str] = None
    timeout_seconds: int = 10


class MCPClient:
    def __init__(self, config: Optional[MCPConfig] = None) -> None:
        self.config = config or MCPConfig(
            endpoint=os.getenv("MCP_ENDPOINT"),
            api_token=os.getenv("MCP_API_TOKEN"),
        )

    def record(self, reservation: ReservationRequest, approval_time: str) -> bool:
        if not self.config.endpoint:
            return False
        response = requests.post(
            self.config.endpoint,
            json={
                "name": f"{reservation.name} {reservation.surname}",
                "car_number": reservation.car_number,
                "reservation_period": reservation.reservation_period,
                "approval_time": approval_time,
            },
            headers={"x-api-token": self.config.api_token or ""},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        return True
