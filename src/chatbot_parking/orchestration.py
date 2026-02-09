"""LangGraph orchestration for the chatbot workflow."""

from dataclasses import dataclass

from langgraph.graph import END, StateGraph

from chatbot_parking.admin_agent import AdminDecision, request_admin_approval
from chatbot_parking.chatbot import ConversationState, ParkingChatbot, ReservationRequest
from chatbot_parking.mcp_client import MCPClient


@dataclass
class WorkflowState:
    conversation: ConversationState
    last_user_input: str | None = None
    intent: str | None = None
    info_response: str | None = None
    reservation_request: ReservationRequest | None = None
    admin_decision: AdminDecision | None = None
    record_success: bool | None = None


def route_intent(state: WorkflowState) -> WorkflowState:
    if state.last_user_input:
        chatbot = ParkingChatbot()
        state.intent = chatbot.detect_intent(state.last_user_input)
    return state


def handle_info(state: WorkflowState) -> WorkflowState:
    if not state.last_user_input:
        return state
    chatbot = ParkingChatbot()
    state.info_response = chatbot.answer_question(state.last_user_input)
    return state


def collect_user_details(state: WorkflowState) -> WorkflowState:
    if not state.last_user_input:
        return state
    chatbot = ParkingChatbot()
    state.conversation = state.conversation or chatbot.start_reservation()
    response, request = chatbot.collect_reservation(state.conversation, state.last_user_input)
    state.info_response = response
    if request:
        state.reservation_request = request
    return state


def admin_approval(state: WorkflowState) -> WorkflowState:
    if state.reservation_request is None:
        return state
    state.admin_decision = request_admin_approval(state.reservation_request)
    return state


def record_reservation(state: WorkflowState) -> WorkflowState:
    if not state.reservation_request or not state.admin_decision:
        return state
    if not state.admin_decision.approved:
        state.record_success = False
        return state
    client = MCPClient()
    try:
        state.record_success = client.record(
            state.reservation_request,
            approval_time=state.admin_decision.decided_at,
        )
    except Exception:
        state.record_success = False
    return state


def build_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("route", route_intent)
    graph.add_node("info", handle_info)
    graph.add_node("collect", collect_user_details)
    graph.add_node("approve", admin_approval)
    graph.add_node("record", record_reservation)

    graph.add_edge("route", "info")
    graph.add_edge("route", "collect")
    graph.add_edge("collect", "approve")
    graph.add_edge("info", END)
    graph.add_edge("approve", "record")
    graph.add_edge("record", END)
    graph.set_entry_point("route")
    return graph


def run_demo() -> WorkflowState:
    chatbot = ParkingChatbot()
    state = WorkflowState(conversation=chatbot.start_reservation())
    state.last_user_input = "I want to book a space"
    response, request = chatbot.collect_reservation(state.conversation, "Alex")
    if request is None:
        response, request = chatbot.collect_reservation(state.conversation, "Morgan")
    if request is None:
        response, request = chatbot.collect_reservation(state.conversation, "XY-1234")
    if request is None:
        response, request = chatbot.collect_reservation(
            state.conversation,
            "2026-02-20 09:00 to 2026-02-20 18:00",
        )
    state.reservation_request = request

    workflow = build_graph().compile()
    return workflow.invoke(state)
