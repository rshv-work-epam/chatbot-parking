"""Command-line interface for demo and interactive chatbot modes."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from chatbot_parking.booking_utils import is_booking_keyword_intent, parse_structured_details
from chatbot_parking.chatbot import ParkingChatbot
from chatbot_parking.orchestration import WorkflowState, build_graph, run_demo


def is_reservation_intent(text: str) -> bool:
    """Return True when the input requests reservation flow."""
    if parse_structured_details(text):
        return True
    return is_booking_keyword_intent(text)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parking chatbot CLI")
    parser.add_argument("--interactive", action="store_true", help="Run interactive CLI mode")
    parser.add_argument("--demo", action="store_true", help="Run the demo scenario")
    return parser.parse_args(argv)


def print_interactive_help() -> None:
    print("Interactive mode commands:")
    print('- Type any question to get an answer (RAG).')
    print('- Type "reserve" (or: book, бронь, забронювати) to start booking wizard.')
    print("- Commands: /help, /exit, /reset")


def run_demo_mode() -> None:
    chatbot = ParkingChatbot()
    print(chatbot.answer_question("What are the working hours and location?"))
    workflow_state = run_demo()
    print("Workflow response:", workflow_state.get("response"))
    print("Admin decision:", workflow_state.get("admin_decision"))


def _run_booking_workflow(booking_inputs: list[str]) -> WorkflowState:
    workflow = build_graph().compile()
    return workflow.invoke(
        WorkflowState(
            user_input="reserve",
            booking_inputs=booking_inputs,
        )
    )


def _run_booking_wizard(
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> tuple[list[str] | None, bool]:
    fields = [
        "Name",
        "Surname",
        "Car number",
        "Reservation period",
    ]
    values: list[str] = []

    output_fn("Starting reservation wizard. Enter /reset to start over or /exit to quit.")
    while len(values) < len(fields):
        user_input = input_fn(f"{fields[len(values)]}: ").strip()
        if user_input == "/exit":
            return (None, True)
        if user_input == "/help":
            print_interactive_help()
            continue
        if user_input == "/reset":
            values.clear()
            output_fn("Booking wizard state reset.")
            continue
        if not user_input:
            output_fn("Value cannot be empty.")
            continue
        values.append(user_input)
    return (values, False)


def run_interactive() -> None:
    chatbot = ParkingChatbot()
    print_interactive_help()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive mode.")
            return

        if not user_input:
            continue
        if user_input == "/exit":
            print("Goodbye!")
            return
        if user_input == "/help":
            print_interactive_help()
            continue
        if user_input == "/reset":
            print("Booking wizard state reset.")
            continue

        if is_reservation_intent(user_input):
            booking_inputs, should_exit = _run_booking_wizard(input, print)
            if should_exit:
                print("Goodbye!")
                return
            if booking_inputs is None:
                continue

            workflow_state = _run_booking_workflow(booking_inputs)
            print("Workflow response:", workflow_state.get("response"))
            print("Admin decision:", workflow_state.get("admin_decision"))
            continue

        print(chatbot.answer_question(user_input))


def run(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.interactive:
        run_interactive()
        return
    run_demo_mode()
