"""Interactive LangGraph workflow with per-thread persistence for chat UI."""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from chatbot_parking.admin_store import (
    create_admin_request,
    get_admin_decision,
)
from chatbot_parking.chatbot import ParkingChatbot
from chatbot_parking.mcp_client import record_reservation

BOOKING_FIELDS: list[str] = ["name", "surname", "car_number", "reservation_period"]
FIELD_PROMPTS: dict[str, str] = {
    "name": "Please provide your name.",
    "surname": "Please provide your surname.",
    "car_number": "What is your car number?",
    "reservation_period": "What reservation period would you like (e.g., 2026-02-20 09:00 to 2026-02-20 18:00)?",
}


class InteractiveState(TypedDict, total=False):
    message: str
    response: str
    mode: Literal["info", "booking"]
    booking_active: bool
    pending_field: str | None
    collected: dict[str, str]
    request_id: str
    status: Literal["collecting", "pending", "approved", "declined"]


def _next_field(current: str | None) -> str | None:
    if current is None:
        return None
    if current not in BOOKING_FIELDS:
        return None
    index = BOOKING_FIELDS.index(current)
    return BOOKING_FIELDS[index + 1] if index + 1 < len(BOOKING_FIELDS) else None


def _is_booking_intent(message: str) -> bool:
    lowered = message.lower()
    booking_keywords = ["book", "reserve", "reservation", "броню", "заброню"]
    return any(keyword in lowered for keyword in booking_keywords)


def _run_turn(state: InteractiveState) -> InteractiveState:
    message = state.get("message", "").strip()
    if not message:
        return {
            "response": "Message cannot be empty.",
            "mode": state.get("mode", "info"),
        }

    booking_active = state.get("booking_active", False)
    pending_field = state.get("pending_field")
    collected = dict(state.get("collected", {}))
    status = state.get("status")
    request_id = state.get("request_id")

    if booking_active and status == "pending" and request_id:
        decision = get_admin_decision(request_id)
        if decision and decision.get("approved") is True:
            record_reservation(
                name=f"{collected.get('name', '').strip()} {collected.get('surname', '').strip()}".strip(),
                car_number=collected.get("car_number", ""),
                reservation_period=collected.get("reservation_period", ""),
                approval_time=decision["decided_at"],
            )
            return {
                "response": "Confirmed and recorded.",
                "mode": "booking",
                "booking_active": False,
                "pending_field": None,
                "collected": collected,
                "request_id": request_id,
                "status": "approved",
            }
        if decision and decision.get("approved") is False:
            return {
                "response": "Declined by administrator.",
                "mode": "booking",
                "booking_active": False,
                "pending_field": None,
                "collected": collected,
                "request_id": request_id,
                "status": "declined",
            }
        return {
            "response": f"Still pending administrator decision. Request id: {request_id}",
            "mode": "booking",
            "booking_active": True,
            "pending_field": None,
            "collected": collected,
            "request_id": request_id,
            "status": "pending",
        }

    if booking_active and pending_field:
        collected[pending_field] = message
        next_field = _next_field(pending_field)
        if next_field is not None:
            return {
                "response": FIELD_PROMPTS[next_field],
                "mode": "booking",
                "booking_active": True,
                "pending_field": next_field,
                "collected": collected,
                "status": "collecting",
            }

        new_request_id = create_admin_request(
            {
                "name": collected["name"],
                "surname": collected["surname"],
                "car_number": collected["car_number"],
                "reservation_period": collected["reservation_period"],
            }
        )
        return {
            "response": f"Submitted for approval. Request id: {new_request_id}",
            "mode": "booking",
            "booking_active": True,
            "pending_field": None,
            "collected": collected,
            "request_id": new_request_id,
            "status": "pending",
        }

    if _is_booking_intent(message):
        return {
            "response": FIELD_PROMPTS["name"],
            "mode": "booking",
            "booking_active": True,
            "pending_field": "name",
            "collected": {},
            "status": "collecting",
        }

    chatbot = ParkingChatbot()
    return {
        "response": chatbot.answer_question(message),
        "mode": "info",
        "booking_active": False,
        "pending_field": None,
        "collected": {},
        "status": "collecting",
    }


def build_interactive_graph(checkpointer=None):
    graph = StateGraph(InteractiveState)
    graph.add_node("turn", _run_turn)
    graph.set_entry_point("turn")
    graph.add_edge("turn", END)
    return graph.compile(checkpointer=checkpointer)


DEFAULT_CHECKPOINTER = InMemorySaver()
DEFAULT_INTERACTIVE_GRAPH = build_interactive_graph(checkpointer=DEFAULT_CHECKPOINTER)
