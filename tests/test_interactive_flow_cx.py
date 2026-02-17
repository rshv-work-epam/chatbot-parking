from chatbot_parking.interactive_flow import default_state, run_chat_turn
from chatbot_parking.persistence import InMemoryPersistence


def _answer_question(_: str) -> str:
    return "info"


def test_review_step_before_admin_submission() -> None:
    persistence = InMemoryPersistence()
    state = default_state() | {
        "booking_active": True,
        "mode": "booking",
        "pending_field": "reservation_period",
        "collected": {
            "name": "Roman",
            "surname": "Shevchuk",
            "car_number": "AA-1234-BB",
        },
        "status": "collecting",
    }

    result, next_state = run_chat_turn(
        message="2026-02-20 09:00 to 2026-02-20 18:00",
        state=state,
        persistence=persistence,
        answer_question=_answer_question,
    )

    assert result["status"] == "review"
    assert result["action_required"] == "review_confirmation"
    assert next_state["request_id"] is None


def test_confirm_in_review_creates_pending_request() -> None:
    persistence = InMemoryPersistence()
    state = default_state() | {
        "booking_active": True,
        "mode": "booking",
        "pending_field": None,
        "collected": {
            "name": "Roman",
            "surname": "Shevchuk",
            "car_number": "AA-1234-BB",
            "reservation_period": "2026-02-20 09:00 to 2026-02-20 18:00",
        },
        "status": "review",
    }

    result, next_state = run_chat_turn(
        message="confirm",
        state=state,
        persistence=persistence,
        answer_question=_answer_question,
    )

    assert result["status"] == "pending"
    assert result["request_id"]
    assert next_state["status"] == "pending"


def test_edit_command_in_review_returns_to_collecting() -> None:
    persistence = InMemoryPersistence()
    state = default_state() | {
        "booking_active": True,
        "mode": "booking",
        "pending_field": None,
        "collected": {
            "name": "Roman",
            "surname": "Shevchuk",
            "car_number": "AA-1234-BB",
            "reservation_period": "2026-02-20 09:00 to 2026-02-20 18:00",
        },
        "status": "review",
    }

    result, next_state = run_chat_turn(
        message="edit car_number",
        state=state,
        persistence=persistence,
        answer_question=_answer_question,
    )

    assert result["status"] == "collecting"
    assert result["pending_field"] == "car_number"
    assert next_state["pending_field"] == "car_number"


def test_outside_working_hours_returns_alternatives() -> None:
    persistence = InMemoryPersistence()
    state = default_state() | {
        "booking_active": True,
        "mode": "booking",
        "pending_field": "reservation_period",
        "collected": {
            "name": "Roman",
            "surname": "Shevchuk",
            "car_number": "AA-1234-BB",
        },
        "status": "collecting",
    }

    result, next_state = run_chat_turn(
        message="2026-02-20 01:00 to 2026-02-20 02:00",
        state=state,
        persistence=persistence,
        answer_question=_answer_question,
    )

    assert result["status"] == "collecting"
    assert "outside working hours" in result["response"]
    assert result.get("alternatives")
    assert next_state["pending_field"] == "reservation_period"
