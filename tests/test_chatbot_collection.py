from chatbot_parking.chatbot import ParkingChatbot


def test_collect_reservation_accepts_structured_multi_field_input() -> None:
    chatbot = ParkingChatbot()
    state = chatbot.start_reservation()

    response, req = chatbot.collect_reservation(
        state,
        "name: Roman; surname: Shevchuk; car: AA-1234-BB; period: 2026-02-20 09:00 to 2026-02-20 18:00",
    )

    assert "ask an administrator" in response
    assert req is not None
    assert req.name == "Roman"
    assert req.surname == "Shevchuk"
    assert req.car_number == "AA-1234-BB"


def test_collect_reservation_reprompts_on_invalid_value() -> None:
    chatbot = ParkingChatbot()
    state = chatbot.start_reservation()

    response, req = chatbot.collect_reservation(state, "123")

    assert req is None
    assert response.startswith("Invalid name:")
