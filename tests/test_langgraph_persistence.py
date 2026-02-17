from langgraph.checkpoint.memory import InMemorySaver

from chatbot_parking.interactive_orchestration import build_interactive_graph


def test_interactive_graph_persists_booking_state_per_thread():
    graph = build_interactive_graph(checkpointer=InMemorySaver())

    first = graph.invoke(
        {"message": "I want to reserve a parking spot"},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert first["mode"] == "booking"
    assert first["response"] == "Please provide your name."

    second = graph.invoke(
        {"message": "Alex"},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert second["response"] == "Please provide your surname."

    other_thread = graph.invoke(
        {"message": "Alex"},
        config={"configurable": {"thread_id": "t2"}},
    )
    assert other_thread["mode"] == "info"
    assert "Please provide your surname." != other_thread["response"]


def test_new_booking_clears_stale_request_id():
    graph = build_interactive_graph(checkpointer=InMemorySaver())

    # finish one booking to set request_id
    graph.invoke({"message": "reserve spot"}, config={"configurable": {"thread_id": "t1"}})
    graph.invoke({"message": "Alex"}, config={"configurable": {"thread_id": "t1"}})
    graph.invoke({"message": "Morgan"}, config={"configurable": {"thread_id": "t1"}})
    graph.invoke({"message": "XY-1234"}, config={"configurable": {"thread_id": "t1"}})
    review = graph.invoke(
        {"message": "2026-02-20 09:00 to 2026-02-20 18:00"},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert review.get("status") == "review"
    pending = graph.invoke(
        {"message": "confirm"},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert pending.get("request_id")

    # start a new booking on same thread; should not leak old request_id
    restarted = graph.invoke(
        {"message": "I want to reserve again"},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert restarted["response"] == "Please provide your name."
    assert restarted.get("request_id") is None
