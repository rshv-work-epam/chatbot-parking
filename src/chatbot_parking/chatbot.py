"""Core chatbot logic for interacting with users."""

from dataclasses import dataclass, field
from typing import Optional

from chatbot_parking.dynamic_data import get_dynamic_info
from chatbot_parking.guardrails import SensitiveDataDetector, filter_sensitive
from chatbot_parking.rag import build_vector_store, retrieve


@dataclass
class ReservationRequest:
    name: str
    surname: str
    car_number: str
    reservation_period: str


@dataclass
class ConversationState:
    pending_field: Optional[str] = None
    collected: dict = field(default_factory=dict)


class ParkingChatbot:
    def __init__(self) -> None:
        self.vector_store = build_vector_store()
        self.guardrails = SensitiveDataDetector()

    def answer_question(self, question: str) -> str:
        dynamic = get_dynamic_info()
        retrieval = retrieve(question, self.vector_store)
        snippets = [doc.page_content for doc in retrieval.documents]
        safe_snippets = filter_sensitive(snippets, detector=self.guardrails)
        response_parts = [
            "Here is what I found:",
            *safe_snippets,
            (
                f"Current availability: {dynamic.available_spaces} spaces. "
                f"Hours: {dynamic.working_hours}. Pricing: {dynamic.pricing}."
            ),
        ]
        return "\n".join(response_parts)

    def detect_intent(self, user_input: str) -> str:
        lowered = user_input.lower()
        booking_keywords = ["reserve", "book", "брон", "reservation", "booking"]
        if any(keyword in lowered for keyword in booking_keywords):
            return "booking"
        return "info"

    def start_reservation(self) -> ConversationState:
        return ConversationState(pending_field="name")

    def collect_reservation(self, state: ConversationState, user_input: str) -> tuple[str, Optional[ReservationRequest]]:
        if state.pending_field is None:
            return ("Reservation is already complete.", self._build_request(state))

        state.collected[state.pending_field] = user_input.strip()
        next_field = self._next_field(state.pending_field)
        state.pending_field = next_field

        if next_field is None:
            return ("Thanks! I have all the details and will ask an administrator for approval.", self._build_request(state))

        prompt = {
            "surname": "Please provide your surname.",
            "car_number": "What is your car number?",
            "reservation_period": "What reservation period would you like (e.g., 2026-02-20 09:00 to 2026-02-20 18:00)?",
        }
        return (prompt[next_field], None)

    def _next_field(self, current_field: str) -> Optional[str]:
        order = ["name", "surname", "car_number", "reservation_period"]
        try:
            current_index = order.index(current_field)
        except ValueError:
            return None
        return order[current_index + 1] if current_index + 1 < len(order) else None

    def _build_request(self, state: ConversationState) -> Optional[ReservationRequest]:
        if len(state.collected) < 4:
            return None
        return ReservationRequest(
            name=state.collected["name"],
            surname=state.collected["surname"],
            car_number=state.collected["car_number"],
            reservation_period=state.collected["reservation_period"],
        )
