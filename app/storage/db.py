from __future__ import annotations

import sqlite3
from pathlib import Path
import os


def resolve_db_path(db_path: str | None = None) -> str:
    if db_path:
        return db_path
    env_path = os.getenv("DB_PATH")
    if env_path:
        return env_path
    data_dir = os.getenv("DATA_DIR")
    if data_dir:
        base_dir = Path(data_dir)
    else:
        base_dir = Path(__file__).resolve().parents[2] / "data" / "db"
    base_dir.mkdir(parents=True, exist_ok=True)
    return str(base_dir / "transactions.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path(db_path))
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            mp_id TEXT PRIMARY KEY,
            occurred_at TEXT NOT NULL,
            amount REAL NOT NULL,
            direction TEXT NOT NULL,
            description_primary TEXT NOT NULL,
            description_secondary TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            raw_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mp_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            suggested_description TEXT,
            suggested_category TEXT,
            suggested_nickname TEXT,
            final_description TEXT,
            final_category TEXT,
            final_nickname TEXT,
            telegram_chat_id TEXT,
            telegram_message_id TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (mp_id) REFERENCES transactions (mp_id)
        )
        """
    )
    conn.commit()
