"""Dynamic data access for availability, hours, and pricing."""

from dataclasses import dataclass
import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "parking.db"


def _get_db_path() -> Path:
    return Path(os.getenv("PARKING_DB_PATH", str(DEFAULT_DB_PATH)))


@dataclass
class DynamicInfo:
    working_hours: str
    pricing: str
    available_spaces: int


def initialize_db() -> None:
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_status (
                id INTEGER PRIMARY KEY,
                working_hours TEXT NOT NULL,
                pricing TEXT NOT NULL,
                available_spaces INTEGER NOT NULL
            )
            """
        )
        row = connection.execute("SELECT COUNT(*) FROM parking_status").fetchone()
        if row and row[0] == 0:
            connection.execute(
                "INSERT INTO parking_status (working_hours, pricing, available_spaces) "
                "VALUES (?, ?, ?)",
                ("Mon-Sun 06:00-23:00", "$2/hour or $15/day", 42),
            )
            connection.commit()


def get_dynamic_info() -> DynamicInfo:
    initialize_db()
    with sqlite3.connect(_get_db_path()) as connection:
        row = connection.execute(
            "SELECT working_hours, pricing, available_spaces FROM parking_status LIMIT 1"
        ).fetchone()
        if not row:
            return DynamicInfo("Unknown", "Unknown", 0)
        return DynamicInfo(row[0], row[1], row[2])
