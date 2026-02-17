from chatbot_parking.interactive_flow import default_state, run_chat_turn
from chatbot_parking.persistence import InMemoryPersistence


def _answer_question(_: str) -> str:
    return "info"


def test_invalid_name_keeps_same_field() -> None:
    persistence = InMemoryPersistence()
    state = default_state() | {"booking_active": True, "mode": "booking", "pending_field": "name"}
    result, next_state = run_chat_turn(
        message="1",
        state=state,
        persistence=persistence,
        answer_question=_answer_question,
    )
    assert "Invalid name" in result["response"]
    assert next_state["pending_field"] == "name"


def test_invalid_car_number_reprompts() -> None:
    persistence = InMemoryPersistence()
    state = default_state() | {
        "booking_active": True,
        "mode": "booking",
        "pending_field": "car_number",
        "collected": {"name": "Roman", "surname": "Shevchuk"},
    }
    result, next_state = run_chat_turn(
        message="???",
        state=state,
        persistence=persistence,
        answer_question=_answer_question,
    )
    assert "Invalid car_number" in result["response"]
    assert next_state["pending_field"] == "car_number"


def test_invalid_period_reprompts() -> None:
    persistence = InMemoryPersistence()
    state = default_state() | {
        "booking_active": True,
        "mode": "booking",
        "pending_field": "reservation_period",
        "collected": {"name": "Roman", "surname": "Shevchuk", "car_number": "AA1234AA"},
    }
    result, next_state = run_chat_turn(
        message="2026-02-20 18:00 to 2026-02-20 09:00",
        state=state,
        persistence=persistence,
        answer_question=_answer_question,
    )
    assert "Invalid reservation_period" in result["response"]
    assert next_state["pending_field"] == "reservation_period"
