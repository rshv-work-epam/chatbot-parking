from chatbot_parking.persistence import InMemoryPersistence


def test_in_memory_persistence_thread_approval_and_reservation_round_trip():
    persistence = InMemoryPersistence()

    persistence.upsert_thread("t-1", {"mode": "booking", "status": "collecting"})
    assert persistence.get_thread("t-1") == {"mode": "booking", "status": "collecting"}

    request_id = persistence.create_approval(
        {
            "name": "Alex",
            "surname": "Morgan",
            "car_number": "XY-1234",
            "reservation_period": "2026-02-20 09:00 to 2026-02-20 18:00",
        }
    )

    pending = persistence.list_pending_approvals()
    assert len(pending) == 1
    assert pending[0]["request_id"] == request_id

    decision = persistence.set_approval_decision(request_id, approved=True, notes="ok")
    assert decision is not None
    assert decision["approved"] is True

    saved = persistence.append_reservation(
        name="Alex Morgan",
        car_number="XY-1234",
        reservation_period="2026-02-20 09:00 to 2026-02-20 18:00",
        approval_time=decision["decided_at"],
        request_id=request_id,
    )

    assert saved["request_id"] == request_id
    assert persistence.reservations
