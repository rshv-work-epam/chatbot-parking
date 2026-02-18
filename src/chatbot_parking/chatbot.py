"""Core chatbot logic for interacting with users."""

from dataclasses import dataclass, field
import os
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
from chatbot_parking.guardrails import (
    contains_prompt_injection,
    is_system_prompt_request,
    filter_sensitive,
    safe_output,
)
from chatbot_parking.rag import (
    build_vector_store,
    classify_intent,
    generate_answer,
    generate_fallback_answer,
    keyword_context,
    retrieve,
)


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
        # Avoid failing fast on startup if an embedding provider is unavailable.
        # The chatbot can fall back to deterministic keyword-based answers.
        try:
            self.vector_store = build_vector_store(insert_documents=False)
        except Exception:
            self.vector_store = None

    def detect_intent(self, question: str) -> str:
        parsed = parse_structured_details(question)
        if parsed:
            return "booking"

        try:
            llm_intent = classify_intent(question)
            if llm_intent in {"booking", "info"}:
                return llm_intent
        except Exception:
            pass

        if is_booking_keyword_intent(question):
            return "booking"

        return "info"

    def answer_question(self, question: str) -> str:
        max_chars = int(os.getenv("MAX_MESSAGE_CHARS", "2000"))
        if max_chars > 0 and len(question) > max_chars:
            return "Message is too long. Please shorten it and try again."

        if is_system_prompt_request(question):
            return "Sorry, I can't share internal instructions."

        if contains_prompt_injection(question):
            return "Sorry, I can't help with that request."

        dynamic = get_dynamic_info()
        max_context = int(os.getenv("MAX_RAG_CONTEXT_CHARS", "6000"))
        context = ""
        retrieval_docs = []

        if self.vector_store is not None:
            try:
                retrieval = retrieve(question, self.vector_store)
                retrieval_docs = list(retrieval.documents)
                snippets = [doc.page_content for doc in retrieval_docs]
                safe_snippets = filter_sensitive(snippets)
                context = "\n".join(safe_snippets) if safe_snippets else ""
            except Exception:
                # Embeddings/vector store failed. Fall back to deterministic context.
                context = keyword_context(question, max_chars=max_context)
        else:
            context = keyword_context(question, max_chars=max_context)

        if max_context > 0 and len(context) > max_context:
            context = context[:max_context].rstrip()
        dynamic_info = (
            f"Current availability: {dynamic.available_spaces} spaces. "
            f"Hours: {dynamic.working_hours}. Pricing: {dynamic.pricing}."
        )
        try:
            response = generate_answer(question, context, dynamic_info)
        except Exception:
            response = generate_fallback_answer(question, dynamic_info)
        if os.getenv("RAG_INCLUDE_SOURCES", "false").strip().lower() == "true":
            source_ids: list[str] = []
            for doc in retrieval_docs:
                source_id = doc.metadata.get("source_id") or doc.metadata.get("id")
                if source_id:
                    rendered = str(source_id)
                    if rendered not in source_ids:
                        source_ids.append(rendered)
            if source_ids:
                response = f"{response}\n\nSources: {', '.join(source_ids)}"

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
