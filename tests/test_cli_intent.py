from chatbot_parking.cli import is_reservation_intent


def test_reservation_intent_true() -> None:
    assert is_reservation_intent("reserve a spot") is True


def test_reservation_intent_false() -> None:
    assert is_reservation_intent("What are your prices?") is False
