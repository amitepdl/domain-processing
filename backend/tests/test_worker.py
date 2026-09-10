from __future__ import annotations

import threading
import uuid
from unittest.mock import patch

from app.db.repository import (
    create_job_with_domains,
    get_job,
    persist_domain_result,
    try_claim_domain,
)
from app.db import connect
from app.worker import handle_message


def _create_pending_domain(db, name: str):
    job = create_job_with_domains(db, [name])
    db.commit()
    domain_id = uuid.UUID(job["to_publish"][0]["domain_id"])
    return job, domain_id


def test_successful_processing_and_ack_path(db):
    job, domain_id = _create_pending_domain(db, "ok.example.test")
    claimed = try_claim_domain(db, domain_id)
    assert claimed is not None
    db.commit()
    changed = persist_domain_result(
        db,
        domain_id,
        success=True,
        ip_addresses=["1.2.3.4"],
        dns_records={"A": ["1.2.3.4"]},
        http_status=200,
        title="OK",
        response_time_ms=12,
        error_type=None,
        error_message=None,
    )
    db.commit()
    assert changed is True
    stored = get_job(db, job["id"])
    assert stored["completed_domains"] == 1
    assert stored["status"] == "COMPLETED"


def test_failed_processing_still_completes_job(db):
    job, domain_id = _create_pending_domain(db, "bad.example.test")
    try_claim_domain(db, domain_id)
    db.commit()
    persist_domain_result(
        db,
        domain_id,
        success=False,
        ip_addresses=[],
        dns_records={},
        http_status=None,
        title=None,
        response_time_ms=None,
        error_type="DNS resolution failed",
        error_message="NXDOMAIN",
    )
    db.commit()
    stored = get_job(db, job["id"])
    assert stored["failed_domains"] == 1
    assert stored["completed_domains"] == 0
    assert stored["status"] == "COMPLETED"


def test_idempotent_duplicate_delivery_does_not_double_count(db):
    job, domain_id = _create_pending_domain(db, "once.example.test")
    try_claim_domain(db, domain_id)
    db.commit()
    kwargs = dict(
        success=True,
        ip_addresses=["1.2.3.4"],
        dns_records={"A": ["1.2.3.4"]},
        http_status=200,
        title="OK",
        response_time_ms=9,
        error_type=None,
        error_message=None,
    )
    assert persist_domain_result(db, domain_id, **kwargs) is True
    db.commit()
    assert persist_domain_result(db, domain_id, **kwargs) is False
    db.commit()
    stored = get_job(db, job["id"])
    assert stored["completed_domains"] == 1


def test_concurrent_duplicate_domain_processing(db):
    _, domain_id = _create_pending_domain(db, "race.example.test")
    db.commit()
    results: list = []

    def claim():
        conn = connect()
        try:
            results.append(try_claim_domain(conn, domain_id))
            conn.commit()
        finally:
            conn.close()

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    claimed = [row for row in results if row is not None]
    assert len(claimed) == 1


def test_worker_acks_already_completed_without_reprocessing(db):
    job, domain_id = _create_pending_domain(db, "done.example.test")
    try_claim_domain(db, domain_id)
    db.commit()
    persist_domain_result(
        db,
        domain_id,
        success=True,
        ip_addresses=["1.2.3.4"],
        dns_records={"A": ["1.2.3.4"]},
        http_status=200,
        title="OK",
        response_time_ms=1,
        error_type=None,
        error_message=None,
    )
    db.commit()

    with patch("app.worker.process_domain") as process:
        handle_message({"domain_id": str(domain_id), "domain": "done.example.test"})
        process.assert_not_called()
    assert get_job(db, job["id"])["completed_domains"] == 1
