"""LangGraph orchestration for the chatbot workflow."""

from dataclasses import dataclass, field

from langgraph.graph import END, StateGraph

from chatbot_parking.admin_agent import AdminDecision, request_admin_approval_tool
from chatbot_parking.chatbot import ConversationState, ParkingChatbot, ReservationRequest
from chatbot_parking.mcp_client import record_reservation

CHATBOT = ParkingChatbot()


@dataclass
class WorkflowState:
    user_input: str
    booking_inputs: list[str] = field(default_factory=list)
    conversation: ConversationState | None = None
    reservation_request: ReservationRequest | None = None
    admin_decision: AdminDecision | None = None
    response: str | None = None
    record_time: str | None = None


def request_admin_approval(reservation: ReservationRequest) -> AdminDecision:
    """Request a decision from the admin approval tool.

    Kept as a module-level function for compatibility with tests and callers
    that monkeypatch this symbol directly.
    """

    decision = request_admin_approval_tool.invoke(
        {
            "name": reservation.name,
            "surname": reservation.surname,
            "car_number": reservation.car_number,
            "reservation_period": reservation.reservation_period,
        }
    )
    return AdminDecision(
        approved=decision["approved"],
        decided_at=decision["decided_at"],
        notes=decision.get("notes"),
    )


def route_intent(state: WorkflowState) -> WorkflowState:
    intent = CHATBOT.detect_intent(state.user_input)
    if intent == "info":
        state.response = CHATBOT.answer_question(state.user_input)
        return state
    state.conversation = CHATBOT.start_reservation()
    return state


def collect_user_details(state: WorkflowState) -> WorkflowState:
    if state.conversation is None:
        return state
    while state.booking_inputs and state.conversation.pending_field is not None:
        user_input = state.booking_inputs.pop(0)
        response, request = CHATBOT.collect_reservation(state.conversation, user_input)
        state.response = response
        if request is not None:
            state.reservation_request = request
            break
    if state.reservation_request is None and state.conversation.pending_field is not None:
        state.response = "Missing reservation details. Please provide all required fields."
    return state


def admin_approval(state: WorkflowState) -> WorkflowState:
    if state.reservation_request is None:
        return state
    state.admin_decision = request_admin_approval(state.reservation_request)
    return state


def record_booking(state: WorkflowState) -> WorkflowState:
    if state.reservation_request is None or state.admin_decision is None:
        return state
    if not state.admin_decision.approved:
        state.response = "Your reservation was declined by an administrator."
        return state
    state.record_time = record_reservation(
        name=f"{state.reservation_request.name} {state.reservation_request.surname}",
        car_number=state.reservation_request.car_number,
        reservation_period=state.reservation_request.reservation_period,
        approval_time=state.admin_decision.decided_at,
    )
    state.response = "Your reservation is confirmed and recorded."
    return state


def _intent_branch(state: WorkflowState) -> str:
    if state.response is not None and state.conversation is None:
        return END
    return "collect"


def _booking_branch(state: WorkflowState) -> str:
    if state.reservation_request is None:
        return END
    return "approve"


def _approval_branch(state: WorkflowState) -> str:
    if state.admin_decision is None:
        return END
    return "record"


def build_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("route", route_intent)
    graph.add_node("collect", collect_user_details)
    graph.add_node("approve", admin_approval)
    graph.add_node("record", record_booking)

    graph.set_entry_point("route")
    graph.add_conditional_edges("route", _intent_branch, {END: END, "collect": "collect"})
    graph.add_conditional_edges("collect", _booking_branch, {END: END, "approve": "approve"})
    graph.add_conditional_edges("approve", _approval_branch, {END: END, "record": "record"})
    graph.add_edge("record", END)
    return graph


def run_demo() -> WorkflowState:
    return run_workflow(
        user_input="I want to book a parking spot",
        booking_inputs=[
            "Alex",
            "Morgan",
            "XY-1234",
            "2026-02-20 09:00 to 2026-02-20 18:00",
        ],
    )


def run_workflow(user_input: str, booking_inputs: list[str]) -> WorkflowState:
    workflow = build_graph().compile()
    return workflow.invoke(
        WorkflowState(
            user_input=user_input,
            booking_inputs=booking_inputs,
        )
    )
