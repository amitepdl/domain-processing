from __future__ import annotations

import pytest
import psycopg

from app.config import DATABASE_URL
from app.db import connect, migrate
from app.db.repository import reset_schema


def postgres_is_up() -> bool:
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture
def db():
    if not postgres_is_up():
        pytest.skip("PostgreSQL is required for this test")
    migrate()
    conn = connect()
    reset_schema(conn)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()
