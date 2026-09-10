from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.jobs import router
from app.db.repository import get_domain, persist_domain_result, try_claim_domain

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@patch("app.api.jobs.publish_domain_jobs")
def test_same_domain_across_jobs_is_processed_once(publish, db):
    first = client.post("/jobs", json={"domains": ["shared.dedup.test"]}).json()
    second = client.post("/jobs", json={"domains": ["shared.dedup.test"]}).json()

    assert publish.call_count == 1
    domain_id = uuid.UUID(publish.call_args[0][0][0]["domain_id"])
    assert try_claim_domain(db, domain_id)
    persist_domain_result(
        db,
        domain_id,
        success=True,
        ip_addresses=["9.9.9.9"],
        dns_records={"A": ["9.9.9.9"]},
        http_status=200,
        title="Shared",
        response_time_ms=20,
        error_type=None,
        error_message=None,
    )
    db.commit()

    job_a = client.get(f"/jobs/{first['job_id']}").json()
    job_b = client.get(f"/jobs/{second['job_id']}").json()
    assert job_a["status"] == "completed"
    assert job_b["status"] == "completed"
    assert job_a["results"][0]["ip_addresses"] == ["9.9.9.9"]
    assert job_b["results"][0]["ip_addresses"] == ["9.9.9.9"]
    assert get_domain(db, domain_id)["domain"] == "shared.dedup.test"
