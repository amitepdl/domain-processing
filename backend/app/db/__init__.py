from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL, RETRY_INTERVAL_SECONDS, RETRY_MAX_ATTEMPTS


def wait_for_database() -> None:
    last_error: Exception | None = None
    for _ in range(RETRY_MAX_ATTEMPTS):
        try:
            with psycopg.connect(DATABASE_URL) as conn:
                conn.execute("SELECT 1")
            return
        except Exception as exc:  # noqa: BLE001 — retry any connect failure
            last_error = exc
            time.sleep(RETRY_INTERVAL_SECONDS)
    raise RuntimeError(f"PostgreSQL was not ready: {last_error}") from last_error


def migrate() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text()
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        applied = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = %s",
            ("001_initial",),
        ).fetchone()
        if applied:
            return
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s)",
            ("001_initial",),
        )


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
