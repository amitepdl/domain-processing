from __future__ import annotations

import uuid

from app.db.repository import (
    create_job_with_domains,
    get_job,
    persist_domain_result,
    try_claim_domain,
)


def _result(success: bool, **overrides):
    payload = dict(
        success=success,
        ip_addresses=["1.2.3.4"] if success else [],
        dns_records={"A": ["1.2.3.4"]} if success else {},
        http_status=200 if success else None,
        title="OK" if success else None,
        response_time_ms=10 if success else None,
        error_type=None if success else "DNS resolution failed",
        error_message=None if success else "NXDOMAIN",
    )
    payload.update(overrides)
    return payload


def test_job_progress_increments_then_completes(db):
    names = ["a.progress.test", "b.progress.test", "c.progress.test"]
    job = create_job_with_domains(db, names)
    db.commit()
    domain_ids = [uuid.UUID(item["domain_id"]) for item in job["to_publish"]]
    assert len(domain_ids) == 3

    try_claim_domain(db, domain_ids[0])
    persist_domain_result(db, domain_ids[0], **_result(True))
    db.commit()
    stored = get_job(db, job["id"])
    assert stored["completed_domains"] == 1
    assert stored["failed_domains"] == 0
    assert stored["status"] == "PROCESSING"

    try_claim_domain(db, domain_ids[1])
    persist_domain_result(db, domain_ids[1], **_result(True))
    try_claim_domain(db, domain_ids[2])
    persist_domain_result(db, domain_ids[2], **_result(True))
    db.commit()
    stored = get_job(db, job["id"])
    assert stored["completed_domains"] == 3
    assert stored["status"] == "COMPLETED"


def test_mixed_success_and_failure_completes_job(db):
    names = ["ok-one.progress.test", "ok-two.progress.test", "bad.progress.test"]
    job = create_job_with_domains(db, names)
    db.commit()
    domain_ids = [uuid.UUID(item["domain_id"]) for item in job["to_publish"]]

    try_claim_domain(db, domain_ids[0])
    persist_domain_result(db, domain_ids[0], **_result(True))
    try_claim_domain(db, domain_ids[1])
    persist_domain_result(db, domain_ids[1], **_result(True))
    try_claim_domain(db, domain_ids[2])
    persist_domain_result(db, domain_ids[2], **_result(False))
    db.commit()

    stored = get_job(db, job["id"])
    assert stored["completed_domains"] == 2
    assert stored["failed_domains"] == 1
    assert stored["status"] == "COMPLETED"
