"""Dynamic data access for availability, hours, and pricing."""

from dataclasses import dataclass
import sqlite3
from pathlib import Path

DB_PATH = Path("data/parking.db")


@dataclass
class DynamicInfo:
    working_hours: str
    pricing: str
    available_spaces: int


def initialize_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
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
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            "SELECT working_hours, pricing, available_spaces FROM parking_status LIMIT 1"
        ).fetchone()
        if not row:
            return DynamicInfo("Unknown", "Unknown", 0)
        return DynamicInfo(row[0], row[1], row[2])
