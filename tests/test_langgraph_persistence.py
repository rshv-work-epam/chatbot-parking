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
