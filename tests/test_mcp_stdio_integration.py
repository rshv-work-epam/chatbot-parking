import sys

from chatbot_parking.mcp_client import record_reservation


def test_mcp_stdio_records_reservation_to_file(tmp_path, monkeypatch) -> None:
    out_file = tmp_path / "reservations.txt"
    monkeypatch.setenv("RESERVATIONS_FILE_PATH", str(out_file))
    monkeypatch.setenv("MCP_SERVER_COMMAND", sys.executable)
    monkeypatch.setenv(
        "MCP_SERVER_ARGS",
        "-m chatbot_parking.mcp_servers.reservations_stdio_server",
    )

    fixed_time = "2026-02-17T12:00:00+00:00"
    decided_at = record_reservation(
        name="John Doe",
        car_number="AA-1234",
        reservation_period="2026-02-20 09:00 to 2026-02-20 10:00",
        approval_time=fixed_time,
    )

    assert decided_at == fixed_time
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert f"John Doe | AA-1234 | 2026-02-20 09:00 to 2026-02-20 10:00 | {fixed_time}" in content

