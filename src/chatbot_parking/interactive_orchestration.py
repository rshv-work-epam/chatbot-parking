"""Interactive workflow with per-thread persistence for chat UI."""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from chatbot_parking.chatbot import ParkingChatbot
from chatbot_parking.interactive_flow import run_chat_turn
from chatbot_parking.persistence import IN_MEMORY_PERSISTENCE

CHATBOT = ParkingChatbot()


class InteractiveState(TypedDict, total=False):
    message: str
    response: str
    mode: Literal["info", "booking"]
    booking_active: bool
    pending_field: str | None
    collected: dict[str, str]
    request_id: str | None
    status: Literal["collecting", "review", "pending", "approved", "declined", "cancelled"]
    recorded: bool
    mcp_recorded: bool
    action_required: str
    progress: dict
    review_summary: str
    alternatives: list[str]
    status_detail: str
    decided_at: str | None


def _run_turn(state: InteractiveState) -> InteractiveState:
    result, next_state = run_chat_turn(
        message=state.get("message", ""),
        state=state,
        persistence=IN_MEMORY_PERSISTENCE,
        answer_question=CHATBOT.answer_question,
        detect_intent=CHATBOT.detect_intent,
    )
    return {
        **next_state,
        "response": result.get("response", ""),
        "mode": result.get("mode", "info"),
        "status": result.get("status", "collecting"),
        "request_id": result.get("request_id"),
        "action_required": result.get("action_required"),
        "progress": result.get("progress"),
        "review_summary": result.get("review_summary"),
        "alternatives": result.get("alternatives"),
        "status_detail": result.get("status_detail"),
        "decided_at": result.get("decided_at"),
    }


def build_interactive_graph(checkpointer=None):
    graph = StateGraph(InteractiveState)
    graph.add_node("turn", _run_turn)
    graph.set_entry_point("turn")
    graph.add_edge("turn", END)
    return graph.compile(checkpointer=checkpointer)


DEFAULT_CHECKPOINTER = InMemorySaver()
DEFAULT_INTERACTIVE_GRAPH = build_interactive_graph(checkpointer=DEFAULT_CHECKPOINTER)
