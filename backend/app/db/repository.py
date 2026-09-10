from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.config import CLAIM_STALE_SECONDS


def create_job_with_domains(
    conn: psycopg.Connection,
    normalized_domains: list[str],
) -> dict[str, Any]:
    job_id = uuid.uuid4()
    total = len(normalized_domains)
    already_completed = 0
    already_failed = 0
    to_publish: list[dict[str, Any]] = []

    with conn.transaction():
        conn.execute(
            """
            INSERT INTO jobs (id, status, total_domains, completed_domains, failed_domains)
            VALUES (%s, 'PENDING', %s, 0, 0)
            """,
            (job_id, total),
        )

        for domain_name in normalized_domains:
            domain_row, inserted = _get_or_create_domain_locked(conn, domain_name)
            conn.execute(
                """
                INSERT INTO job_domains (job_id, domain_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (job_id, domain_row["id"]),
            )
            status = domain_row["status"]
            if status == "COMPLETED":
                already_completed += 1
            elif status == "FAILED":
                already_failed += 1
            elif status == "PENDING":
                to_publish.append(
                    {"domain_id": str(domain_row["id"]), "domain": domain_row["domain"]}
                )

        job_status = "PENDING"
        if already_completed + already_failed == total:
            job_status = "COMPLETED"
        elif already_completed + already_failed > 0:
            job_status = "PROCESSING"

        conn.execute(
            """
            UPDATE jobs
            SET completed_domains = %s,
                failed_domains = %s,
                status = %s
            WHERE id = %s
            """,
            (already_completed, already_failed, job_status, job_id),
        )

    job = get_job(conn, job_id)
    job["to_publish"] = to_publish
    return job


def _get_or_create_domain_locked(
    conn: psycopg.Connection, domain_name: str
) -> tuple[dict[str, Any], bool]:
    existing = conn.execute(
        "SELECT * FROM domains WHERE domain = %s FOR UPDATE",
        (domain_name,),
    ).fetchone()
    if existing:
        return existing, False

    domain_id = uuid.uuid4()
    try:
        with conn.transaction():
            row = conn.execute(
                """
                INSERT INTO domains (id, domain, status)
                VALUES (%s, %s, 'PENDING')
                RETURNING *
                """,
                (domain_id, domain_name),
            ).fetchone()
            return row, True
    except psycopg.errors.UniqueViolation:
        row = conn.execute(
            "SELECT * FROM domains WHERE domain = %s FOR UPDATE",
            (domain_name,),
        ).fetchone()
        if not row:
            raise
        return row, False


def list_jobs(conn: psycopg.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, created_at, status, total_domains, completed_domains, failed_domains
        FROM jobs
        ORDER BY created_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_job(conn: psycopg.Connection, job_id: uuid.UUID) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, created_at, status, total_domains, completed_domains, failed_domains
        FROM jobs
        WHERE id = %s
        """,
        (job_id,),
    ).fetchone()
    return dict(row) if row else None


def get_job_with_results(
    conn: psycopg.Connection, job_id: uuid.UUID
) -> dict[str, Any] | None:
    job = get_job(conn, job_id)
    if not job:
        return None
    results = conn.execute(
        """
        SELECT
            d.domain,
            d.status,
            d.ip_addresses,
            d.dns_records,
            d.http_status,
            d.title,
            d.response_time_ms,
            d.error_type,
            d.error_message,
            d.processed_at
        FROM job_domains jd
        JOIN domains d ON d.id = jd.domain_id
        WHERE jd.job_id = %s
        ORDER BY d.domain
        """,
        (job_id,),
    ).fetchall()
    job["results"] = [dict(row) for row in results]
    return job


def try_claim_domain(
    conn: psycopg.Connection, domain_id: uuid.UUID
) -> dict[str, Any] | None:
    with conn.transaction():
        row = conn.execute(
            """
            UPDATE domains
            SET status = 'PROCESSING',
                claimed_at = NOW()
            WHERE id = %s
              AND (
                    status = 'PENDING'
                    OR (
                        status = 'PROCESSING'
                        AND (
                            claimed_at IS NULL
                            OR claimed_at < NOW() - (%s * INTERVAL '1 second')
                        )
                    )
              )
            RETURNING *
            """,
            (domain_id, CLAIM_STALE_SECONDS),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE jobs
            SET status = 'PROCESSING'
            WHERE id IN (
                SELECT job_id FROM job_domains WHERE domain_id = %s
            )
              AND status = 'PENDING'
            """,
            (domain_id,),
        )
        return dict(row)


def get_domain(conn: psycopg.Connection, domain_id: uuid.UUID) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM domains WHERE id = %s", (domain_id,)).fetchone()
    return dict(row) if row else None


def persist_domain_result(
    conn: psycopg.Connection,
    domain_id: uuid.UUID,
    *,
    success: bool,
    ip_addresses: list[str] | None,
    dns_records: dict[str, Any] | None,
    http_status: int | None,
    title: str | None,
    response_time_ms: int | None,
    error_type: str | None,
    error_message: str | None,
) -> bool:
    terminal = "COMPLETED" if success else "FAILED"
    with conn.transaction():
        updated = conn.execute(
            """
            UPDATE domains
            SET status = %s,
                ip_addresses = %s,
                dns_records = %s,
                http_status = %s,
                title = %s,
                response_time_ms = %s,
                error_type = %s,
                error_message = %s,
                processed_at = NOW()
            WHERE id = %s
              AND status = 'PROCESSING'
            RETURNING id
            """,
            (
                terminal,
                Jsonb(ip_addresses) if ip_addresses is not None else None,
                Jsonb(dns_records) if dns_records is not None else None,
                http_status,
                title,
                response_time_ms,
                error_type,
                error_message,
                domain_id,
            ),
        ).fetchone()
        if not updated:
            return False

        if success:
            conn.execute(
                """
                UPDATE jobs
                SET completed_domains = completed_domains + 1,
                    status = CASE
                        WHEN completed_domains + 1 + failed_domains >= total_domains
                            THEN 'COMPLETED'::job_status
                        ELSE 'PROCESSING'::job_status
                    END
                WHERE id IN (
                    SELECT job_id FROM job_domains WHERE domain_id = %s
                )
                """,
                (domain_id,),
            )
        else:
            conn.execute(
                """
                UPDATE jobs
                SET failed_domains = failed_domains + 1,
                    status = CASE
                        WHEN completed_domains + failed_domains + 1 >= total_domains
                            THEN 'COMPLETED'::job_status
                        ELSE 'PROCESSING'::job_status
                    END
                WHERE id IN (
                    SELECT job_id FROM job_domains WHERE domain_id = %s
                )
                """,
                (domain_id,),
            )
        return True


def reset_schema(conn: psycopg.Connection) -> None:
    conn.execute("TRUNCATE job_domains, domains, jobs")


def serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    created_at = job["created_at"]
    if isinstance(created_at, datetime):
        created_at_value = created_at.isoformat()
    else:
        created_at_value = created_at
    payload = {
        "job_id": str(job["id"]),
        "status": str(job["status"]).lower(),
        "total_domains": job["total_domains"],
        "completed_domains": job["completed_domains"],
        "failed_domains": job["failed_domains"],
        "created_at": created_at_value,
    }
    if "results" in job:
        payload["results"] = [serialize_domain_result(row) for row in job["results"]]
    return payload


def serialize_domain_result(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "domain": row["domain"],
        "status": str(row["status"]).lower(),
    }
    if row.get("ip_addresses") is not None:
        result["ip_addresses"] = row["ip_addresses"]
    if row.get("dns_records") is not None:
        result["dns"] = row["dns_records"]
    if row.get("http_status") is not None:
        result["http_status"] = row["http_status"]
    if row.get("title") is not None:
        result["title"] = row["title"]
    if row.get("response_time_ms") is not None:
        result["response_time_ms"] = row["response_time_ms"]
    if row.get("error_type") or row.get("error_message"):
        result["error"] = {
            "type": row.get("error_type"),
            "message": row.get("error_message"),
        }
    return result
