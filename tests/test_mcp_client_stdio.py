from pathlib import Path

from chatbot_parking.mcp_client import record_reservation


def test_record_reservation_uses_stdio_mcp(monkeypatch, tmp_path):
    target = tmp_path / "reservations.txt"

    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.delenv("MCP_ALLOW_LOCAL_FALLBACK", raising=False)
    monkeypatch.setenv("RESERVATIONS_FILE_PATH", str(target))

    approval_time = record_reservation(
        name="Alex Morgan",
        car_number="XY-1234",
        reservation_period="2026-02-20 09:00 to 2026-02-20 18:00",
    )

    assert target.exists()
    line = target.read_text(encoding="utf-8").strip()
    assert "Alex Morgan | XY-1234" in line
    assert approval_time in line
