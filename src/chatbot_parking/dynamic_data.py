"""Dynamic data access for availability, hours, and pricing."""

from dataclasses import dataclass
import os
import sqlite3
from pathlib import Path

DEFAULT_WORKING_HOURS = os.getenv("PARKING_WORKING_HOURS", "Mon-Sun 06:00-23:00")
DEFAULT_PRICING = os.getenv("PARKING_PRICING", "$2/hour or $15/day")
DEFAULT_AVAILABLE_SPACES = int(os.getenv("PARKING_AVAILABLE_SPACES", "42"))

DEFAULT_DB_PATH = Path.cwd() / "data" / "parking.db"
FALLBACK_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "parking.db"
TMP_DB_PATH = Path("/tmp/parking.db")


def _get_db_path() -> Path:
    env = os.getenv("PARKING_DB_PATH")
    if env:
        return Path(env)

    candidates = [Path("/app/data/parking.db"), DEFAULT_DB_PATH, FALLBACK_DB_PATH]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Prefer a writable location by default. Container images often run as a non-root user
    # and cannot create /app/data at runtime, so fall back to /tmp.
    for candidate in (DEFAULT_DB_PATH, TMP_DB_PATH):
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if os.access(candidate.parent, os.W_OK):
                return candidate
        except Exception:
            continue

    return TMP_DB_PATH


@dataclass
class DynamicInfo:
    working_hours: str
    pricing: str
    available_spaces: int


def _connect(db_path: Path) -> sqlite3.Connection:
    # In containers we run as non-root; repo files under /app/data may be read-only.
    # If the file exists but isn't writable, open it in read-only mode.
    if db_path.exists() and not os.access(db_path, os.W_OK):
        return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    return sqlite3.connect(db_path)


def initialize_db() -> None:
    db_path = _get_db_path()
    if db_path.exists() and not os.access(db_path, os.W_OK):
        # Best-effort: use pre-packaged DB if present, without attempting to migrate/create.
        return
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
                (DEFAULT_WORKING_HOURS, DEFAULT_PRICING, DEFAULT_AVAILABLE_SPACES),
            )
            connection.commit()


def get_dynamic_info() -> DynamicInfo:
    try:
        initialize_db()
        db_path = _get_db_path()
        with _connect(db_path) as connection:
            row = connection.execute(
                "SELECT working_hours, pricing, available_spaces FROM parking_status LIMIT 1"
            ).fetchone()
            if not row:
                return DynamicInfo(DEFAULT_WORKING_HOURS, DEFAULT_PRICING, DEFAULT_AVAILABLE_SPACES)
            return DynamicInfo(row[0], row[1], row[2])
    except Exception:
        # Never fail the chat flow because dynamic data is unavailable.
        return DynamicInfo(DEFAULT_WORKING_HOURS, DEFAULT_PRICING, DEFAULT_AVAILABLE_SPACES)
