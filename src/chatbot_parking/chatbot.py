"""Core chatbot logic for interacting with users."""

from dataclasses import dataclass, field
from typing import Optional

from chatbot_parking.booking_utils import (
    BOOKING_FIELDS,
    apply_valid_parsed_details,
    is_booking_keyword_intent,
    next_missing_field,
    normalize_car_number,
    normalize_reservation_period,
    parse_structured_details,
    validate_field,
)
from chatbot_parking.dynamic_data import get_dynamic_info
from chatbot_parking.guardrails import filter_sensitive, safe_output
from chatbot_parking.rag import build_vector_store, classify_intent, generate_answer, retrieve


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
        self.vector_store = build_vector_store(insert_documents=False)

    def detect_intent(self, question: str) -> str:
        parsed = parse_structured_details(question)
        if parsed:
            return "booking"

        if is_booking_keyword_intent(question):
            return "booking"

        try:
            llm_intent = classify_intent(question)
            if llm_intent in {"booking", "info"}:
                return llm_intent
        except Exception:
            pass

        return "info"

    def answer_question(self, question: str) -> str:
        dynamic = get_dynamic_info()
        retrieval = retrieve(question, self.vector_store)
        snippets = [doc.page_content for doc in retrieval.documents]
        safe_snippets = filter_sensitive(snippets)
        context = "\n".join(safe_snippets) if safe_snippets else "No relevant context found."
        dynamic_info = (
            f"Current availability: {dynamic.available_spaces} spaces. "
            f"Hours: {dynamic.working_hours}. Pricing: {dynamic.pricing}."
        )
        response = generate_answer(question, context, dynamic_info)
        return safe_output(response)

    def start_reservation(self) -> ConversationState:
        return ConversationState(pending_field="name")

    def collect_reservation(self, state: ConversationState, user_input: str) -> tuple[str, Optional[ReservationRequest]]:
        if state.pending_field is None:
            return ("Reservation is already complete.", self._build_request(state))
        text = user_input.strip()
        parsed = parse_structured_details(text)
        if parsed:
            state.collected = apply_valid_parsed_details(state.collected, parsed)
            state.pending_field = next_missing_field(state.collected)
            if state.pending_field is None:
                return (
                    "Thanks! I have all the details and will ask an administrator for approval.",
                    self._build_request(state),
                )
            return (self._prompt_for_field(state.pending_field), None)

        error = validate_field(state.pending_field, text)
        if error:
            return (f"Invalid {state.pending_field}: {error} {self._prompt_for_field(state.pending_field)}", None)

        if state.pending_field == "car_number":
            state.collected[state.pending_field] = normalize_car_number(text)
        elif state.pending_field == "reservation_period":
            state.collected[state.pending_field] = normalize_reservation_period(text)
        else:
            state.collected[state.pending_field] = text

        state.pending_field = self._next_field(state.pending_field)
        if state.pending_field is None:
            return (
                "Thanks! I have all the details and will ask an administrator for approval.",
                self._build_request(state),
            )

        return (self._prompt_for_field(state.pending_field), None)

    def _next_field(self, current_field: str) -> Optional[str]:
        try:
            current_index = BOOKING_FIELDS.index(current_field)
        except ValueError:
            return None
        return (
            BOOKING_FIELDS[current_index + 1]
            if current_index + 1 < len(BOOKING_FIELDS)
            else None
        )

    def _prompt_for_field(self, field: str) -> str:
        prompts = {
            "name": "Please provide your name.",
            "surname": "Please provide your surname.",
            "car_number": "What is your car number?",
            "reservation_period": "What reservation period would you like (e.g., 2026-02-20 09:00 to 2026-02-20 18:00)?",
        }
        return prompts[field]

    def _build_request(self, state: ConversationState) -> Optional[ReservationRequest]:
        if len(state.collected) < 4:
            return None
        return ReservationRequest(
            name=state.collected["name"],
            surname=state.collected["surname"],
            car_number=state.collected["car_number"],
            reservation_period=state.collected["reservation_period"],
        )
