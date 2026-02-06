"""LangGraph orchestration for the chatbot workflow."""

from dataclasses import dataclass

from langgraph.graph import END, StateGraph

from chatbot_parking.admin_agent import AdminDecision, request_admin_approval
from chatbot_parking.chatbot import ConversationState, ParkingChatbot, ReservationRequest


@dataclass
class WorkflowState:
    conversation: ConversationState
    reservation_request: ReservationRequest | None = None
    admin_decision: AdminDecision | None = None


def collect_user_details(state: WorkflowState) -> WorkflowState:
    return state


def admin_approval(state: WorkflowState) -> WorkflowState:
    if state.reservation_request is None:
        return state
    state.admin_decision = request_admin_approval(state.reservation_request)
    return state


def build_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("collect", collect_user_details)
    graph.add_node("approve", admin_approval)

    graph.add_edge("collect", "approve")
    graph.add_edge("approve", END)
    graph.set_entry_point("collect")
    return graph


def run_demo() -> WorkflowState:
    chatbot = ParkingChatbot()
    state = WorkflowState(conversation=chatbot.start_reservation())
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
