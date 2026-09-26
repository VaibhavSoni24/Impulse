"""Database connection factory and initialization utilities for IMPULSE."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from typing import Generator

from local.evaluation.schema import CURRENT_SCHEMA_VERSION, init_schema

DEFAULT_DB_PATH = Path("experiments/evaluation.db")


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Creates a new SQLite connection with foreign keys enabled and Row factory configured."""
    target_path = Path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    """Initializes the SQLite evaluation database with the complete schema.

    Returns the resolved path of the initialized database.
    """
    target_path = Path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(target_path)
    try:
        init_schema(conn)
    finally:
        conn.close()

    return target_path


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Returns the user_version PRAGMA recorded in the database."""
    cur = conn.cursor()
    cur.execute("PRAGMA user_version;")
    row = cur.fetchone()
    return int(row[0]) if row else 0
