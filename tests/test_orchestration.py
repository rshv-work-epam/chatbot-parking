from chatbot_parking.admin_agent import AdminDecision
from chatbot_parking.orchestration import WorkflowState, build_graph


def test_happy_path_records_booking(monkeypatch):
    def fake_admin(_reservation):
        return AdminDecision(approved=True, decided_at="2025-01-01T00:00:00Z")

    def fake_record(**_kwargs):
        return "2025-01-01T00:00:00Z"

    monkeypatch.setattr("chatbot_parking.orchestration.request_admin_approval", fake_admin)
    monkeypatch.setattr("chatbot_parking.orchestration.record_reservation", fake_record)

    workflow = build_graph().compile()
    state = workflow.invoke(
        WorkflowState(
            user_input="Please reserve a spot",
            booking_inputs=["Alex", "Morgan", "XY-1234", "2026-02-20 09:00 to 2026-02-20 18:00"],
        )
    )

    assert state["response"] == "Your reservation is confirmed and recorded."
    assert state["record_time"] == "2025-01-01T00:00:00Z"


def test_deny_path(monkeypatch):
    def fake_admin(_reservation):
        return AdminDecision(approved=False, decided_at="2025-01-01T00:00:00Z", notes="Denied")

    monkeypatch.setattr("chatbot_parking.orchestration.request_admin_approval", fake_admin)

    workflow = build_graph().compile()
    state = workflow.invoke(
        WorkflowState(
            user_input="Please reserve a spot",
            booking_inputs=["Alex", "Morgan", "XY-1234", "2026-02-20 09:00 to 2026-02-20 18:00"],
        )
    )

    assert state["response"] == "Your reservation was declined by an administrator."


def test_incomplete_booking(monkeypatch):
    def fake_admin(_reservation):
        return AdminDecision(approved=True, decided_at="2025-01-01T00:00:00Z")

    monkeypatch.setattr("chatbot_parking.orchestration.request_admin_approval", fake_admin)

    workflow = build_graph().compile()
    state = workflow.invoke(
        WorkflowState(
            user_input="Please reserve a spot",
            booking_inputs=["Alex"],
        )
    )

    assert state["response"] == "Missing reservation details. Please provide all required fields."
